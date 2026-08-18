# Call Center Radar Wiki

This wiki is the working handbook for the Call Center Radar POC.

## What This Project Is

Call Center Radar is an evidence-first call intelligence POC for support and operations teams. The product turns call recordings into manager-ready insights with traceable evidence, synchronized audio and transcript playback, and prioritized actions.

## Project Objective

The objective of this POC is to process support-call recordings, identify which calls need manager attention, explain every important AI decision with real evidence, and present the result through a manager-friendly dashboard.

For the POC, the product should prove that it can:

- accept a new call recording
- generate evidence-backed call analysis
- rank important calls for manager review
- show exactly why a call was flagged

## Sample Data

The current sample dataset contains:

- `1441` audio files
- `1441` metadata JSON files
- one metadata file paired to each call by shared call ID

The sample metadata includes agent details, caller details, timestamps, speaker IDs, response timing, and quality-related labels such as MOS and script scores.

Core positioning:

- Bank-grade call intelligence where every AI judgment can be verified
- SQLite for the POC
- Hybrid LLM plus deterministic validation
- Simple manager UI, technically defensible architecture

## Core Product Promise

- Trust: every important judgment links back to transcript turns and audio evidence
- Speed: quick dashboard workflow for a demo and POC
- Action: manager brief, recommended action, and Radar Priority scoring

## Main Product Screens

- Manager dashboard with ranked call queue
- Call Detail as the centerpiece proof screen
- Issue Radar for recurring issue groups
- Customer Journey timeline for repeat callers
- Agent view for treatment and satisfaction support signals

## POC Delivery Model

This POC is being built through vertical feature slices, not frontend/backend ownership splits.

- One person handles the initial setup
- After setup, both contributors work on full-stack, testable stories
- Each story should be demoable and verifiable on its own

## Required Diagrams

See [Architecture and Delivery Plan](Architecture-and-Delivery-Plan).

## Pages

- [Architecture and Delivery Plan](Architecture-and-Delivery-Plan)
