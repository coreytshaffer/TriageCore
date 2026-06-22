# OpenClaw Boundary

## Status

Documentation-only boundary note for CR-043. No OpenClaw dependency is added in
 this slice.

## Purpose

Define the safest initial boundary for OpenClaw interoperability inside
 TriageCore.

## Core Position

OpenClaw is a subordinate external runtime, not a policy authority.

TriageCore decides. OpenClaw acts only after TriageCore permits.

External runtimes may request capability, but only TriageCore grants
 authority. No external tool permission is TriageCore authorization.

## Why OpenClaw Is A Good First Example

OpenClaw has enough channel, tool, automation, and execution surface to be
 useful. It also has enough risk surface to make the doctrine meaningful.

## Default Boundary

Allowed without approval:

- receive a message or event
- normalize it into a `TaskPacket`
- propose a draft response
- summarize approved read-only context

Blocked without approval:

- shell execution
- file mutation
- browser actions
- plugin or skill loading
- email or calendar mutation
- credential access
- cloud model routing
- scheduled automation

## Initial Architecture

```text
User or channel
    |
    v
OpenClaw adapter
    |
    v
TriageCore TaskPacket
    |
    v
Policy and privacy checks
    |
    v
Approval gate
    |
    v
Bounded execution receipt
    |
    v
Audit ledger evidence
```

## Provenance Expectations

OpenClaw-originated actions should eventually record runtime identity, version,
 channel or gateway, tool profile, sandbox state, model provider, approval
 record, and the linked TriageCore `TaskPacket` identifier.

## First Safe Use Case

A read-only remote briefing such as: summarize the repo state and propose the
 next CR.

## Not In CR-043

This slice does not:

- install OpenClaw
- add an adapter implementation
- allow tool execution through OpenClaw
- add any network-facing service
- grant any new mutation authority
