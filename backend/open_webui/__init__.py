"""Open WebUI command line entry point, retained for non-Docker self-hosting."""

import argparse


def app():
    parser = argparse.ArgumentParser(description='ChatLDT')
    parser.add_argument('command', choices=['serve', 'dev'], nargs='?', default='serve')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--version', action='store_true')
    args = parser.parse_args()
    if args.version:
        from open_webui.env import VERSION

        print(f'ChatLDT version: {VERSION}')
        return
    import uvicorn

    uvicorn.run(
        'open_webui.main:app',
        host=args.host,
        port=args.port,
        reload=args.command == 'dev',
        workers=1,
        forwarded_allow_ips='127.0.0.1',
    )


if __name__ == '__main__':
    app()
