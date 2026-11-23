# Plan: two dashboards

**Status: agreed. On 2026-11-19 the owner said to go ahead with this plan, in the order of work below.
SR-SuiteMaker is being built first; the Local analysis dashboard follows it.**

A mock-up and a diagram of this plan are on the design canvas ("Plan — two dashboards" and "Mock-up — Local
analysis dashboard"): <https://claude.ai/artifact/8qNks7eM7wySai6Nj2iZjq>

## The idea

ShakeReady would have two dashboards, because there are two different questions.

| | Regional analysis | Local analysis |
|---|---|---|
| The question | What happens across a whole inventory? | What does one site need for analysis? |
| You give it | A hazard layer | A site and a target spectrum |
| You get | Damage probabilities for every structure | A suite of ground motions |
| Its parts | Inventory, Hazard, Damage | Site, Hazard, Target, Suite |
| The tool behind it | SR-HazardMaker | SR-SuiteMaker |

Each dashboard has three parts that read in the order you work. The tools remain tools, each with its own
repository, command line and citation; the dashboards are where their results are used.

## The link between them

A bridge on the regional dashboard would carry an "Analyze this site" link. It opens the local dashboard with
the bridge's location and, when a scenario is displayed, that earthquake's magnitude and the bridge's distance
to the fault. From "which bridges are at risk in this earthquake" to "the ground motions for analyzing this one".

## The menu

Home · Regional analysis · Local analysis · Tools · Data · Methods · Projects · Publications · People

"Tools" would replace "Code" and hold SR-HazardMaker, SR-SuiteMaker and the other codes. Old addresses keep
working. "Local analysis" does not go in the menu as an empty page.

## Order of work

1. **SR-SuiteMaker.** Done and tested: the targets; the record-set format; the selection (matching a
   target's mean, or its mean and spread). Still to do: reading the NGA-West2 flatfile and the group's
   simulated motions (both need files from the owner); then the tool itself (browser page, command line,
   outputs, public repository, citation).
2. **Local analysis.** Live since 2026-11-23 with Site, Hazard, Disaggregation and Target, the hazard asked
   of USGS directly. The Suite part is next.
3. **The link and the menu.**

## What exists today

- The regional dashboard is live (`dashboard.html`, called "Regional analysis" in the menu), and its panel
  has the three parts, Inventory, Hazard and Damage. It stays.
- SR-SuiteMaker's first stage is in a private repository, <https://github.com/TRG-UCLA/SR-SuiteMaker>.

## Open questions for the owner

- Are the three parts of Local analysis right: Site, Target, Suite? Should there be a fourth, such as the
  structure's response?
- Which code checks should a suite be reported against (for example ASCE 7, ASCE 41, bridge design criteria)?
- What Local analysis needs to know about a structure beyond its period.
