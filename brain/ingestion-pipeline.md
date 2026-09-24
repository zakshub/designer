# Continuous Intelligence Ingestion Pipeline

## Goal

Turn external design knowledge into source grounded reusable reasoning for agents without creating an untraceable content dump.

## Pipeline

Discover
Search authoritative sources, practitioner material, conferences, studios, award archives, design systems, research and current industry practice.

Qualify
Score source authority, originality, relevance, recency and evidence quality.

Extract
Capture atomic principles, methods, heuristics, patterns, anti patterns, examples and context.

Normalize
Map each item to shared taxonomy such as UX, UI, typography, branding, motion, accessibility, research, systems, implementation and creative direction.

Deduplicate
Merge identical claims while retaining all supporting sources.

Contrast
Detect disagreement between experts, standards or schools of thought and preserve the disagreement.

Synthesize
Convert raw observations into reusable decision rules with clear conditions and exceptions.

Validate
Check against standards, usability evidence, production constraints and contradictory evidence.

Promote
Move reviewed intelligence into canonical skill or principle files.

Expire
Flag time sensitive platform guidance for revalidation rather than allowing stale rules to persist indefinitely.

## Intelligence object

id
title
principle
domain
problem
context
when_to_use
when_not_to_use
evidence
sources
experts
confidence
counterpoints
examples
related_skills
last_verified

## Agent behavior

When solving a design task, the agent should retrieve relevant skills first, then standards, then expert intelligence and references. It should synthesize a context specific decision rather than averaging every source equally.

## Future automation

A scheduled research workflow can continuously discover newly published standards, major design system changes, practitioner talks, award winning case studies and emerging interaction patterns. New material should enter a review queue before becoming canonical.
