## Agent: analysis_agent

```mermaid
graph TD
    ac74d7eb["GOAL_CREATED (ac74d7eb)"]
    81494bce["REASONING_STEP (81494bce)"]
    900abf16["TOOL_INVOKED (900abf16)"]
    395ab8d2["REASONING_STEP (395ab8d2)"]
    8400b4d6["GOAL_COMPLETED (8400b4d6)"]
    395ab8d2 --> 8400b4d6
    900abf16 --> 395ab8d2
    ac74d7eb --> 81494bce
    81494bce --> 900abf16
```


## Agent: citation_agent

```mermaid
graph TD
    d8d1ab15["GOAL_CREATED (d8d1ab15)"]
    b4689343["REASONING_STEP (b4689343)"]
    1495adeb["TOOL_INVOKED (1495adeb)"]
    fa176302["REASONING_STEP (fa176302)"]
    9391e759["GOAL_COMPLETED (9391e759)"]
    1495adeb --> fa176302
    d8d1ab15 --> b4689343
    b4689343 --> 1495adeb
    fa176302 --> 9391e759
```


## Agent: ingestion_agent

```mermaid
graph TD
    eb56e2bc["GOAL_CREATED (eb56e2bc)"]
    9759ce2a["REASONING_STEP (9759ce2a)"]
    62c4ebe0["TOOL_INVOKED (62c4ebe0)"]
    cd03cca3["REASONING_STEP (cd03cca3)"]
    a6b8e7df["GOAL_COMPLETED (a6b8e7df)"]
    eb56e2bc --> 9759ce2a
    cd03cca3 --> a6b8e7df
    9759ce2a --> 62c4ebe0
    62c4ebe0 --> cd03cca3
```


## Agent: synthesis_agent

```mermaid
graph TD
    d1cf9da7["GOAL_CREATED (d1cf9da7)"]
    0bca3b47["REASONING_STEP (0bca3b47)"]
    3d97f921["TOOL_INVOKED (3d97f921)"]
    a3cfd26c["REASONING_STEP (a3cfd26c)"]
    dbb32835["GOAL_COMPLETED (dbb32835)"]
    d1cf9da7 --> 0bca3b47
    0bca3b47 --> 3d97f921
    3d97f921 --> a3cfd26c
    a3cfd26c --> dbb32835
```
