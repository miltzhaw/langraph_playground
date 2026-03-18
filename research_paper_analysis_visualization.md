## Agent: analysis_agent

```mermaid
graph TD
    a95f5169["GOAL_CREATED (a95f5169)"]
    aee24afc["REASONING_STEP (aee24afc)"]
    c72aadbf["TOOL_INVOKED (c72aadbf)"]
    639589e7["REASONING_STEP (639589e7)"]
    a92d2c39["GOAL_COMPLETED (a92d2c39)"]
    639589e7 --> a92d2c39
    a95f5169 --> aee24afc
    aee24afc --> c72aadbf
    c72aadbf --> 639589e7
```


## Agent: citation_agent

```mermaid
graph TD
    200b1e0b["GOAL_CREATED (200b1e0b)"]
    b6bcb9b8["REASONING_STEP (b6bcb9b8)"]
    884ed84f["TOOL_INVOKED (884ed84f)"]
    19a958f0["REASONING_STEP (19a958f0)"]
    0a193c42["GOAL_COMPLETED (0a193c42)"]
    200b1e0b --> b6bcb9b8
    b6bcb9b8 --> 884ed84f
    884ed84f --> 19a958f0
    19a958f0 --> 0a193c42
```


## Agent: ingestion_agent

```mermaid
graph TD
    5dea4c41["GOAL_CREATED (5dea4c41)"]
    4952bcf7["REASONING_STEP (4952bcf7)"]
    ec92dc39["TOOL_INVOKED (ec92dc39)"]
    9fd8b086["REASONING_STEP (9fd8b086)"]
    ebd9b7b9["GOAL_COMPLETED (ebd9b7b9)"]
    5dea4c41 --> 4952bcf7
    4952bcf7 --> ec92dc39
    9fd8b086 --> ebd9b7b9
```


## Agent: synthesis_agent

```mermaid
graph TD
    7789309c["GOAL_CREATED (7789309c)"]
    70d39e4b["REASONING_STEP (70d39e4b)"]
    1e77ae42["TOOL_INVOKED (1e77ae42)"]
    56427702["REASONING_STEP (56427702)"]
    a0b01608["GOAL_COMPLETED (a0b01608)"]
    7789309c --> 70d39e4b
    56427702 --> a0b01608
    1e77ae42 --> 56427702
    70d39e4b --> 1e77ae42
```
