# Plan: two dashboards

**Status: agreed. On 2026-11-19 the owner said to go ahead with this plan, in the order of work below.
SR-SuiteMaker is being built first; the Local analysis dashboard follows it.**

A mock-up and a diagram of this plan are on the design canvas ("Plan — two dashboards" and "Mock-up — Local
analysis dashboard"): <https://claude.ai/artifact/8qNks7eM7wySai6Nj2iZjq>

## Reorganization asked for by the owner on 2026-11-23 (supersedes parts of what follows)

The owner redefined Local analysis and the tools around it. **Not yet built; design questions are open.**

- **Local analysis** becomes: bring a suite (which may be a single motion), bring a model, analyze damage
  and loss. Models are, for now, OpenSees models.
- **SR-SuiteMaker becomes a tool of its own**, like SR-HazardMaker: site, hazard, disaggregation, target,
  suite. What `local.html` does today (hazard, disaggregation, target) is the front half of that tool and
  moves to it. Its output, a suite, is brought to Local analysis.
- **SR-ModelMaker is a new tool**: bring your own OpenSees model, see it and edit it if necessary; or make
  an OpenSees model from scratch.

So the site is symmetric: Regional analysis takes an inventory and a hazard layer (SR-HazardMaker) and
gives damage; Local analysis takes a suite (SR-SuiteMaker) and a model (SR-ModelMaker) and gives response,
damage and loss.

Told to the owner, and to be settled with him before building:

1. **Where OpenSees runs.** No build of OpenSees for the browser was found (searched 2026-11-23), so analyses
   cannot run in the page. Choices: the user's own computer (the page prepares a ready-to-run package and
   reads the results back); a remote computer; or a small built-in solver for simple models, labeled as
   not OpenSees.
2. **Bringing a model.** An OpenSees model is a program, not data. Proposed: run the user's script in the
   browser against a stand-in that records nodes and elements instead of solving (Python in the browser
   exists, via Pyodide; Tcl would need an interpreter). Editing means changing properties and exporting a
   flat script, not preserving the original program.
3. **From scratch** means parametric templates for particular kinds of structure, not a general modeler.
4. **Damage and loss** need fragility and consequence data and a method, which are the owner's choices.
5. NHERI SimCenter's tools cover related ground; decide whether to interoperate.

### Decided 2026-11-23: analyses run on the user's own computer first; TACC explored alongside

The owner chose the user's own computer to start, and asked how models could be run at the Texas Advanced
Computing Center, where the group has collaborators who can help with APIs and connections.

**The design rule that follows:** Local analysis produces one **run package** (the model, the motions, a run
script, a manifest) and reads back one **results format**. Running on the user's computer and running at
TACC then differ only in who executes the package. Define those two formats before anything else.

What was found about TACC (DesignSafe training pages, read 2026-11-23):

- TACC's programmable interface is **Tapis** (`https://tacc.tapis.io`). DesignSafe publishes OpenSees apps on
  it: OpenSees-EXPRESS (single core, on a virtual machine, no queue, starts at once), OpenSeesSP and
  OpenSeesMP (Stampede3, through the SLURM queue), and a new OpenSeesPy app (`designsafe-openseespy-s3`).
- A job is submitted by program: authenticate, inspect the app, build a job description (input folder on a
  storage system, main script, cores, wall time, queue, allocation), submit, poll its status, fetch outputs.
  Inputs and outputs live on DesignSafe storage. The Python client is `tapipy`; plain HTTP works too.
- The apps' definitions are open (the WMA-Tapis-Templates repository), so ShakeReady could register an app of
  its own that wraps its run package.

**Questions for the TACC collaborators** (not answerable from documentation):

1. How may a page on another site sign a user in? The examples use a username and password, which a web
   page must never ask for. Is there an authorization-code flow for a registered outside application?
2. Will the Tapis Files and Jobs services accept requests from a browser on another site?
3. Whose allocation pays: each user's own, or one held for ShakeReady?
4. For a suite of 11 to 40 independent runs of one model, what is the recommended pattern: one job per
   motion, one parallel job, or a launcher?
5. Should ShakeReady register its own Tapis app, pinned to an OpenSees version for repeatability?
6. Limits on file staging and polling; whether jobs can notify on completion.

### Decided 2026-11-23: OpenSeesPy only

The owner decided that only OpenSeesPy models are allowed: no Tcl, in SR-ModelMaker, in the run package, or
at TACC. What follows from it:

- **Reading a model:** run the user's Python script in the browser (Pyodide) against a stand-in for
  `openseespy.opensees` that records what is built (nodes, elements, materials, sections, constraints, masses,
  loads) and does nothing for analysis commands. One mechanism reads any Python model however it is written.
  Things to handle: scripts split over several files, scripts that read data files, scripts that import other
  libraries, and scripts that run their own analysis.
- **The run package** is a Python package: the model, the motions, a run script, a manifest. The OpenSeesPy
  version used is recorded with the results.
- **At TACC** the target is DesignSafe's OpenSeesPy app (`designsafe-openseespy-s3`), which is new in 2026;
  ask the collaborators how settled it is.
- A user with a Tcl model must convert it. No automatic conversion is promised.

Still open with the owner: which kind of structure the first from-scratch template is.

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
