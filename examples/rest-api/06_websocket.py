"""WebSocket DSL usage examples for planfile REST API.

Connect to ws://localhost:8000/ws and send DSL commands.
"""

import asyncio
import json


async def example_websocket_basic():
    """Basic WebSocket DSL command execution."""
    import websockets

    uri = "ws://localhost:8000/ws?project_path=."
    async with websockets.connect(uri) as ws:
        # Wait for welcome message
        msg = await ws.recv()
        print("Server:", msg)

        # Send DSL command
        await ws.send('{"command": "list tickets sprint=current"}')

        # Receive response
        response = await ws.recv()
        print("Response:", response)


async def example_websocket_interactive():
    """Interactive WebSocket DSL session."""
    import websockets

    uri = "ws://localhost:8000/ws?project_path=."
    async with websockets.connect(uri) as ws:
        print(await ws.recv())  # Welcome message

        commands = [
            "list tickets sprint=current",
            'create ticket "Fix login bug" priority=high',
            "list sprints",
            "validate"
        ]

        for cmd in commands:
            print(f"\n> {cmd}")
            await ws.send(json.dumps({"command": cmd}))
            response = await ws.recv()
            print(json.loads(response))


async def example_websocket_error_handling():
    """WebSocket with error handling."""
    import websockets

    uri = "ws://localhost:8000/ws?project_path=."
    try:
        async with websockets.connect(uri) as ws:
            print(await ws.recv())

            # Send invalid command
            await ws.send('{"command": "frobnicate things"}')
            response = await ws.recv()
            result = json.loads(response)
            if not result["ok"]:
                print("Error:", result["error"])

    except websockets.exceptions.WebSocketException as e:
        print(f"WebSocket error: {e}")


async def example_websocket_raw_text():
    """Send raw text command (without JSON wrapper)."""
    import websockets

    uri = "ws://localhost:8000/ws?project_path=."
    async with websockets.connect(uri) as ws:
        print(await ws.recv())

        # Send raw text
        await ws.send("list tickets sprint=current status=open")
        response = await ws.recv()
        print(json.loads(response))


async def example_websocket_batch():
    """Batch operations via WebSocket."""
    import websockets

    uri = "ws://localhost:8000/ws?project_path=."
    async with websockets.connect(uri) as ws:
        print(await ws.recv())

        # Mark multiple tickets as done
        for ticket_id in ["PLF-001", "PLF-002", "PLF-003"]:
            await ws.send(f'{{"command": "done ticket {ticket_id}"}}')
            response = await ws.recv()
            print(f"{ticket_id}: {json.loads(response)['ok']}")


async def main():
    """Run WebSocket examples."""
    print("WebSocket DSL Examples")
    print("=" * 40)
    print("Start the server first: uvicorn planfile.api.server:app --reload\n")

    # Uncomment to run examples
    # await example_websocket_basic()
    # await example_websocket_interactive()
    # await example_websocket_error_handling()
    # await example_websocket_raw_text()
    # await example_websocket_batch()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted")
