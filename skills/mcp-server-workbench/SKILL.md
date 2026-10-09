---
name: mcp-server-workbench
description: Guides design, implementation, and verification of MCP servers that connect AI clients to external services. Use when building or improving an MCP server, tool, resource, or prompt integration.
---

# MCP server workbench

Help build an MCP integration around real user tasks, with tools that are understandable, predictable, and verifiable. Use the current protocol and SDK documentation for implementation details; do not treat remembered API shapes as authoritative.

## 1. Define the integration

Establish:

- The service and the user tasks the integration must support.
- The language, client, deployment environment, and required transport, if known.
- Authentication method, scopes, data sensitivity, and actions that change external state.
- Existing code, tests, and project conventions to preserve.

If these facts are missing and affect safety or architecture, ask before implementing. Avoid collecting credentials in chat or placing secrets in source files.

## 2. Research and plan

Consult current authoritative MCP specification and service API documentation. Record relevant protocol version, supported transports, authentication requirements, endpoint limits, and data models. Separate verified behavior from assumptions.

Create an operation inventory. For each candidate capability, note its user value, inputs, outputs, access scope, side effects, and whether it can be paginated. Choose a balanced surface:

- Provide enough focused operations for clients to compose common tasks.
- Add a higher-level operation when it materially simplifies a repeated multi-step workflow.
- Avoid redundant tools and tools whose purpose or side effects cannot be described clearly.

Select a transport and SDK compatible with the deployment target and client requirements. Explain the choice and dependency cost before adding dependencies.

## 3. Design each capability

For each tool, resource, or prompt, specify:

- A distinct name and concise description that helps a model select it correctly.
- Constrained inputs, including validation and meaningful field descriptions.
- A focused output with a predictable structure.
- Pagination or filtering where result size can grow.
- Error outcomes that tell the caller what failed and a safe next step.
- Whether it reads data, changes state, can be repeated safely, or reaches an external system.

Make destructive or externally visible effects explicit. Require confirmation where the user's intent or authorization is uncertain. Apply least-privilege access and never expose more returned data than the task requires.

## 4. Implement in the existing project

Follow the repository's language, SDK, and test conventions. Keep service access, authentication, validation, pagination, and response formatting understandable and reusable. Use asynchronous I/O where appropriate. Do not invent an SDK API; check current documentation or the installed package before relying on a feature.

Provide structured outputs when supported by the chosen SDK and useful to clients. Keep human-readable text concise. Preserve actionable error context without leaking secrets, tokens, or sensitive upstream responses.

## 5. Verify

Use existing project checks first. Verify compilation or syntax, tests, and the server's MCP handshake and capability listing with an available compatible inspector or client. Exercise representative calls, including:

- A normal read request.
- Missing or invalid input.
- An upstream error or empty result.
- Pagination when relevant.
- A write or other side effect, if supported, checking authorization and confirmation behavior.

If a tool is unavailable, explain the limitation and use a safe substitute; do not claim an unrun check passed.

## 6. Evaluate usefulness

Test several independent, realistic user tasks using read-only requests where possible. Check that each task can be completed with the exposed capabilities, that names and descriptions lead to the appropriate calls, and that answers can be verified against service data. Use findings to remove confusing overlaps or fill important capability gaps.

Summarize implemented capabilities, transport and dependency choices, verification performed, security-sensitive operations, and remaining limitations.
