## Agent: analysis_agent

```mermaid
graph TD
    bfc207fc["GOAL_CREATED (bfc207fc)"]
    8308ecb1["REASONING_STEP (8308ecb1)"]
    da92473d["TOOL_INVOKED (da92473d)"]
    be573d3e["REASONING_STEP (be573d3e)"]
    f3568e8b["GOAL_COMPLETED (f3568e8b)"]
    da92473d --> be573d3e
    be573d3e --> f3568e8b
    bfc207fc --> 8308ecb1
    8308ecb1 --> da92473d
```


## Agent: citation_agent

```mermaid
graph TD
    5877ef69["GOAL_CREATED (5877ef69)"]
    11f3cda0["REASONING_STEP (11f3cda0)"]
    eaeca300["TOOL_INVOKED (eaeca300)"]
    8270dabc["REASONING_STEP (8270dabc)"]
    66be5f91["GOAL_COMPLETED (66be5f91)"]
    eaeca300 --> 8270dabc
    5877ef69 --> 11f3cda0
    11f3cda0 --> eaeca300
    8270dabc --> 66be5f91
```


## Agent: ingestion_agent

```mermaid
graph TD
    d30b6ba5["GOAL_CREATED (d30b6ba5)"]
    58913cb1["REASONING_STEP (58913cb1)"]
    b5ccf28c["TOOL_INVOKED (b5ccf28c)"]
    07c7b420["REASONING_STEP (07c7b420)"]
    45e48e21["GOAL_COMPLETED (45e48e21)"]
    58913cb1 --> b5ccf28c
    d30b6ba5 --> 58913cb1
    07c7b420 --> 45e48e21
    b5ccf28c --> 07c7b420
```


## Agent: synthesis_agent

```mermaid
graph TD
    5897cf5a["GOAL_CREATED (5897cf5a)"]
    f2e8e7f6["REASONING_STEP (f2e8e7f6)"]
    f7c7dd01["TOOL_INVOKED (f7c7dd01)"]
    d449e80e["REASONING_STEP (d449e80e)"]
    cb649284["GOAL_COMPLETED (cb649284)"]
    f2e8e7f6 --> f7c7dd01
    d449e80e --> cb649284
    5897cf5a --> f2e8e7f6
    f7c7dd01 --> d449e80e
```
