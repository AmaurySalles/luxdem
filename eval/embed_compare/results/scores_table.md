| Run | n | hit@10 | MRR (gold+acc) | FR hit@10 | DE all hit@10 | DE q41-45 | DE q46-56 | dossier hit@10 | ONH hit@10 |
|---|---|---|---|---|---|---|---|---|---|
| prefix/bge-m3 | 56 | 0.946 | 0.867 | 1.000 | 0.812 (16) | 1.000 (5) | 0.727 (11) | 0.893 | 1.000 |
| postfix/bge-m3 | 56 | 0.946 | 0.870 | 1.000 | 0.812 (16) | 1.000 (5) | 0.727 (11) | 0.893 | 1.000 |
| prefix/snowflake-arctic-embed2 | 56 | 0.982 | 0.910 | 1.000 | 0.938 (16) | 1.000 (5) | 0.909 (11) | 0.964 | 1.000 |
| postfix/snowflake-arctic-embed2 | 56 | 0.982 | 0.910 | 1.000 | 0.938 (16) | 1.000 (5) | 0.909 (11) | 0.964 | 1.000 |
| prefix/nomic-embed-text | 56 | 0.732 | 0.670 | 0.900 | 0.312 (16) | 0.600 (5) | 0.182 (11) | 0.607 | 0.849 |
| postfix/nomic-embed-text | 56 | 0.732 | 0.670 | 0.900 | 0.312 (16) | 0.600 (5) | 0.182 (11) | 0.571 | 0.849 |

| Run | MRR FR | MRR DE all | MRR DE q41-45 | MRR DE q46-56 (gold only) | pooled hit@10 | pooled MRR |
|---|---|---|---|---|---|---|
| prefix/bge-m3 | 0.969 | 0.611 | 0.900 | 0.480 | 0.946 | 0.849 |
| postfix/bge-m3 | 0.969 | 0.624 | 0.900 | 0.498 | 0.946 | 0.852 |
| prefix/snowflake-arctic-embed2 | 1.000 | 0.683 | 1.000 | 0.540 | 0.982 | 0.901 |
| postfix/snowflake-arctic-embed2 | 1.000 | 0.687 | 1.000 | 0.544 | 0.982 | 0.901 |
| prefix/nomic-embed-text | 0.843 | 0.236 | 0.603 | 0.070 | 0.696 | 0.634 |
| postfix/nomic-embed-text | 0.843 | 0.236 | 0.603 | 0.069 | 0.696 | 0.634 |

| Model | compared | hit→miss | miss→hit | miss both |
|---|---|---|---|---|
| bge-m3 | 56 | - | - | q46, q47, q49 |
| snowflake-arctic-embed2 | 56 | - | - | q54 |
| nomic-embed-text | 56 | - | - | q04, q05, q14, q29, q43, q45, q46, q47, q48, q49, q50, q52, q53, q54, q56 |
