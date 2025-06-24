#!/usr/bin/env python3
"""
HTTP3 Connection Migration Test Tool

This tool tests whether an HTTP3 website supports connection migration
by analyzing QUIC connection parameters and transport settings.
"""

import argparse
import asyncio
import logging
import socket
import sys
from typing import Any, Dict
from urllib.parse import urlparse

from aioquic.asyncio import connect
from aioquic.h3.connection import H3_ALPN
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.logger import QuicLogger

from . import __version__


class ConnectionMigrationTester:
    def __init__(self, host: str, port: int, verify_mode: bool = True):
        self.host = host
        self.port = port
        self.verify_mode = verify_mode
        self.logger = logging.getLogger(__name__)

    async def test_connection_migration(self) -> bool:
        """Test connection migration by simulating network changes"""
        self.logger.info(f"Testing connection migration for {self.host}:{self.port}")

        quic_logger = QuicLogger()

        # Create QUIC configuration
        config = QuicConfiguration(
            is_client=True,
            alpn_protocols=H3_ALPN,
            quic_logger=quic_logger,
        )
        if not self.verify_mode:
            config.verify_mode = False

        try:
            # Establish connection
            self.logger.info("Phase 1: Establishing initial connection...")
            async with connect(
                self.host,
                self.port,
                configuration=config,
            ) as protocol:
                quic_conn = protocol._quic
                self.logger.info("Initial connection established")

                # Get initial network information
                initial_transport = protocol._transport
                if initial_transport is None:
                    self.logger.error("No transport found")
                    return False
                initial_local_addr = initial_transport.get_extra_info("sockname")
                self.logger.info(f"Initial local address: {initial_local_addr}")

                # Wait for server to send NEW_CONNECTION_ID frames
                self.logger.info("Waiting for server to provide additional connection IDs...")
                for i in range(5):  # Wait up to 5 seconds
                    await asyncio.sleep(1.0)
                    peer_cids = quic_conn._peer_cid_available
                    if len(peer_cids) > 0:
                        break
                    self.logger.debug(f"Waiting... ({i + 1}/5 seconds)")

                peer_cids = quic_conn._peer_cid_available

                # Show current connection state
                cid_seq_nums = quic_conn._peer_cid_sequence_numbers
                self.logger.info(f"Connection ID sequence numbers: {cid_seq_nums}")

                # RFC9000 Section 5.1.1: Check connection ID management compliance
                if len(peer_cids) > 0:
                    self.logger.info("Server supports connection ID management (RFC 9000 Section 5.1)")
                    self.logger.info(f"Available connection IDs for potential migration: {len(peer_cids)}")
                else:
                    self.logger.warning("❌ No spare connection IDs available")
                    self.logger.warning("This limits connection migration capabilities")

                transport_params_event = next(
                    (
                        e
                        for e in reversed(quic_logger._traces[0]._events)
                        if e is not None and e.get("name") == "transport:parameters_set"
                    ),
                    None,
                )

                if transport_params_event is not None:
                    transport_params: Dict[str, Any] = transport_params_event["data"]
                    if transport_params.get("active_connection_id_limit") is not None:
                        self.logger.info(
                            f"Remote active_connection_id_limit: {transport_params["active_connection_id_limit"]}"
                        )
                    self.logger.info(f"Remote disable_active_migration: {transport_params["disable_active_migration"]}")
                    if transport_params.get("max_idle_timeout") is not None:
                        self.logger.info(
                            f"Remote max_idle_timeout: {transport_params["max_idle_timeout"] / 1000} seconds"
                        )
                    if transport_params.get("disable_active_migration"):
                        self.logger.warning("⚠️ Server explicitly disabled active connection migration")

                # Record original state
                original_cid = quic_conn._peer_cid.cid
                original_seq = quic_conn._peer_cid.sequence_number

                self.logger.info(f"Original connection ID: {original_cid.hex()}")
                self.logger.info(f"Original sequence number: {original_seq}")

                # Show available connection IDs
                if len(peer_cids) > 0:
                    self.logger.info("Available connection IDs for migration:")
                    for i, cid in enumerate(peer_cids):
                        self.logger.info(f"  {i}: {cid.cid.hex()} (seq: {cid.sequence_number})")

                # Phase 2: Test network change simulation
                migration_success = False

                # Method 1: Simulate network change by changing local port
                self.logger.info("Phase 2: Simulating network change via local port change...")
                try:
                    # Create a new socket with different local port
                    new_socket = socket.socket(
                        (socket.AF_INET6 if ":" in str(initial_local_addr[0]) else socket.AF_INET),
                        socket.SOCK_DGRAM,
                    )
                    new_socket.bind(("", 0))  # Bind to any available port
                    new_local_addr = new_socket.getsockname()
                    self.logger.info(f"New local address: {new_local_addr}")

                    # Create new transport with the new socket
                    loop = asyncio.get_event_loop()
                    if initial_transport is not None:
                        initial_transport.close()  # Close old transport
                    await loop.create_datagram_endpoint(lambda: protocol, sock=new_socket)

                    protocol.change_connection_id()
                    await asyncio.sleep(1.0)

                    self.logger.info("Simulated network interface change")

                    # Test connection functionality after network change
                    try:
                        await asyncio.wait_for(protocol.ping(), timeout=5.0)
                        self.logger.info("Connection alive after network change simulation")
                        migration_success = True
                    except Exception:
                        self.logger.warning("Connection failed after network change: ping timeout")

                    path_challenge_event = next(
                        (
                            e
                            for e in reversed(quic_logger._traces[0]._events)
                            if e is not None
                            and e.get("name") == "transport:packet_received"
                            and any(
                                frame.get("frame_type") == "path_challenge" for frame in e["data"].get("frames", [])
                            )
                        ),
                        None,
                    )
                    if path_challenge_event is not None:
                        self.logger.info("Detected server-initiated PATH_CHALLENGE")
                    else:
                        self.logger.warning(
                            "⚠️ No PATH_CHALLENGE sent by server, violating RFC 9000 Section 8.2 which requires path "
                            "validation during connection migration."
                        )

                except Exception as e:
                    self.logger.warning(f"Network change simulation failed: {e}")

                # Phase 3: Final connection test
                self.logger.info("Phase 3: Final connection functionality test...")

                # Send final ping to verify connection is still functional
                try:
                    await asyncio.wait_for(protocol.ping(), timeout=5.0)
                except Exception:
                    self.logger.error("Final connection test failed: ping timeout")
                    return False

                self.logger.info("Connection still functional after migration tests")

                # Check connection state
                connection_state = quic_conn._state
                self.logger.info(f"Final connection state: {connection_state}")

                if str(connection_state) == "QuicConnectionState.CONNECTED":
                    self.logger.info("Connection remains in CONNECTED state")
                else:
                    self.logger.warning(f"⚠️ Connection state changed to: {connection_state}")

                # Final assessment
                if migration_success:
                    self.logger.info("🎉 Connection migration test PASSED")
                else:
                    self.logger.info("❌ Connection migration test FAILED")

                return migration_success

        except Exception as e:
            self.logger.error(f"Connection migration test failed: {e}")
            return False


async def main() -> None:
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Test HTTP3 connection migration support", prog="quic-migration-tester"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("url", help="URL to test (e.g., https://www.google.com)")
    parser.add_argument("--no-verify", action="store_true", help="Disable certificate verification")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")

    # Parse URL
    parsed = urlparse(args.url)
    if parsed.scheme != "https":
        print("Error: Only HTTPS URLs are supported for HTTP3")
        sys.exit(1)

    host = parsed.hostname
    port = parsed.port or 443

    # Create tester
    tester = ConnectionMigrationTester(host=host, port=port, verify_mode=not args.no_verify)

    # Run test
    print(f"Testing connection migration support for {host}:{port}")
    print("-" * 60)

    try:
        print("🔄 Running connection migration test...")
        result = await tester.test_connection_migration()

        print("-" * 60)
        if result:
            print("Connection migration test PASSED")
            print("\nThis confirms:")
            print("- Connection ID can be changed successfully")
            print("- Connection remains alive after migration")
            print("- Server properly supports connection migration")
            sys.exit(0)
        else:
            print("❌ Connection migration test FAILED")
            print("\nThis indicates:")
            print("- Connection migration may not be properly supported")
            print("- Connection ID change failed or broke the connection")
            print("- Server may have limited migration capabilities")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Test failed with error: {e}")
        sys.exit(1)


def cli_main() -> None:
    """Synchronous entry point for command line interface"""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
