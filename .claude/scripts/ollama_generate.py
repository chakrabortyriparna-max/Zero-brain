#!/usr/bin/env python3
"""Call Ollama /api/generate and emit the response to stdout."""

import argparse
import json
import urllib.request


def main():
    parser = argparse.ArgumentParser(description="Call Ollama generate API")
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--format", choices=["json"], help="Force output format")
    parser.add_argument("--stream", action="store_true", default=False)
    args = parser.parse_args()

    payload = {
        "model": args.model,
        "prompt": args.prompt,
        "stream": args.stream,
    }
    if args.format:
        payload["format"] = args.format

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    result = json.load(resp)
    response = result["response"]
    # Strip markdown fences if present
    response = response.strip()
    if response.startswith("```"):
        lines = response.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response = "\n".join(lines).strip()
    print(response)


if __name__ == "__main__":
    main()
