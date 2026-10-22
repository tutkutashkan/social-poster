#!/usr/bin/env python3
"""Sign in to LinkedIn and save a posting token to .env.

LinkedIn tokens last 60 days, so run this again when poster.py warns that the
token is about to expire. Needs LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET
in .env, and http://localhost:8765/callback added as an authorized redirect
URL on the Auth tab of your LinkedIn app.
"""

import datetime as dt
import json
import secrets
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from poster import ROOT, env, http, load_env

PORT = 8765
REDIRECT_URI = f"http://localhost:{PORT}/callback"
SCOPES = "openid profile w_member_social"
ENV_FILE = ROOT / ".env"


def wait_for_callback():
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            if url.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            result.update({k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Done. You can close this tab and go back to the terminal.")

        def log_message(self, *args):
            pass

    with HTTPServer(("localhost", PORT), Handler) as server:
        while "code" not in result and "error" not in result:
            server.handle_request()
    return result


def update_env_file(values):
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    remaining = dict(values)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    lines += [f"{key}={value}" for key, value in remaining.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n")


def main():
    load_env()
    client_id, client_secret = env("LINKEDIN_CLIENT_ID"), env("LINKEDIN_CLIENT_SECRET")
    state = secrets.token_urlsafe(16)
    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT_URI,
        "state": state, "scope": SCOPES,
    })
    print(f"Opening LinkedIn in your browser. If nothing opens, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    result = wait_for_callback()
    if "error" in result:
        sys.exit(f"LinkedIn returned an error: {result.get('error_description', result['error'])}")
    if result.get("state") != state:
        sys.exit("The sign-in response didn't match this request. Run the script again.")

    _, body = http("POST", "https://www.linkedin.com/oauth/v2/accessToken",
                   headers={"Content-Type": "application/x-www-form-urlencoded"},
                   data=urllib.parse.urlencode({
                       "grant_type": "authorization_code", "code": result["code"],
                       "redirect_uri": REDIRECT_URI, "client_id": client_id,
                       "client_secret": client_secret,
                   }).encode())
    token = json.loads(body)
    _, body = http("GET", "https://api.linkedin.com/v2/userinfo",
                   headers={"Authorization": f"Bearer {token['access_token']}"})
    user = json.loads(body)

    expires = dt.date.today() + dt.timedelta(seconds=token["expires_in"])
    update_env_file({
        "LINKEDIN_ACCESS_TOKEN": token["access_token"],
        "LINKEDIN_AUTHOR_URN": f"urn:li:person:{user['sub']}",
        "LINKEDIN_TOKEN_EXPIRES": expires.isoformat(),
    })
    print(f"Saved a token for {user.get('name', 'your account')} to .env. It expires on {expires}.")
    print("If the poster runs on GitHub Actions, update its secrets with: gh secret set -f .env")


if __name__ == "__main__":
    main()
