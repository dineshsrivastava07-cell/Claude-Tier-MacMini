#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createServer }         from "./server.js";

const { server } = createServer();

const transport = new StdioServerTransport();
await server.connect(transport);

// Stderr so it doesn't pollute MCP stdio stream
process.stderr.write("[tier-router-mcp] Server started (stdio transport)\n");
