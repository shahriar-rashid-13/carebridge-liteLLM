"""Vercel entry point for the LiteLLM proxy."""

from dotenv import load_dotenv

load_dotenv()

from litellm.proxy import proxy_server

app = proxy_server.app
