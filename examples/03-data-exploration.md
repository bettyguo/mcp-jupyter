# Example 03 — Data exploration with `inspect`

> The differentiator. The `inspect` tool's three modes give the agent three
> levels of access; the default is the safe one.

## The three modes

```
inspect(target, mode='auto')     # SAFE — type-aware summary (shape, dtypes, head)
inspect(target, mode='summary')  # SAFE — .describe() + value_counts() for tabular types
inspect(target, mode='value')    # UNSAFE — raw repr capped at 50 KB
```

## Typical agent flow

```
User: "What's in df?"
Agent → kernel.list_variables()           # finds `df`
Agent → inspect("df", mode="auto")        # shape, dtypes, head(5)
Agent: "df is a 10k × 6 DataFrame with columns [id, age, ...]; here's a sample of 5 rows."

User: "What's the distribution of country?"
Agent → inspect("df['country']", mode="summary")    # value_counts
Agent: "75% US, 10% UK, 8% DE, 5% FR, 2% JP."

User: "Show me row 42."
Agent → inspect("df.iloc[42]", mode="value")        # explicit user ask → value mode OK
Agent: "<the row repr>"
```

## What the agent shouldn't do

It shouldn't reach for `mode="value"` unprompted. The tool description tells
it so. If you see your agent dumping raw rows without being asked, file an
issue — the description needs sharpening.
