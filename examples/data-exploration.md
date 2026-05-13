# Data exploration with `inspect`

The three modes of `inspect` give the agent three levels of access. The
default is the safe one.

```
inspect(target, mode='auto')     # type-aware summary (shape, dtypes, head)
inspect(target, mode='summary')  # describe / value_counts / numeric stats
inspect(target, mode='value')    # raw repr, capped at 50 KB; sensitive
```

## Typical flow

```
User: "what's in df?"
Agent: kernel.list_variables()          # finds df
       inspect("df", mode="auto")       # shape, dtypes, head
       => "df is a 10k x 6 DataFrame with columns [id, age, ...]; here are 5 rows."

User: "what's the distribution of country?"
Agent: inspect("df['country']", mode="summary")
       => "75% US, 10% UK, 8% DE, 5% FR, 2% JP."

User: "show me row 42."
Agent: inspect("df.iloc[42]", mode="value")  # explicit user request
       => "<the row repr>"
```

## What the agent shouldn't do

Reach for `mode='value'` unprompted. The tool description tells it not
to. If you see your agent dumping raw rows without being asked, the
description needs sharpening; file an issue.
