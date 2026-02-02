# Beck ↔ Berendes rough comparison
- Rough rows: 952 (pairs: 951)
- Generated edges pairs (explicit): 815
- Generated span pairs (inferred): 947

## Pair diffs (rough vs inferred span)
- Rough-only pairs: 13
- Span-only pairs: 9

### Rough-only pairs
- DMM1010 -> e-140 (DMM id is reused (same DMM appears multiple times with different lemmas/targets); span anchors by earliest occurrence.)
- DMM1042 -> e-58 (Not present in generated span; likely manually curated/imputed.)
- DMM1102 -> e-140 (Beck+Berendes row exists but Berendes target is blank; rough attaches it to a Berendes teitok.)
- DMM2184 -> e-XXX (Not present in generated span; likely manually curated/imputed.)
- DMM3041 -> e-455 (Beck+Berendes row exists but Berendes target is blank; rough attaches it to a Berendes teitok.)
- DMM3061 -> e-476 (Beck+Berendes row exists but Berendes target is blank; rough attaches it to a Berendes teitok.)
- DMM3075 -> e-493 (Beck+Berendes row exists but Berendes target is blank; rough attaches it to a Berendes teitok.)
- DMM4032 -> e-613 (Beck+Berendes row exists but Berendes target is blank; rough attaches it to a Berendes teitok.)
- DMM4086 -> e-667 (Beck+Berendes row exists but Berendes target is blank; rough attaches it to a Berendes teitok.)
- DMM4133 -> e-715 (Beck+Berendes row exists but Berendes target is blank; rough attaches it to a Berendes teitok.)
- DMM4156 -> e-739 (Beck+Berendes row exists but Berendes target is blank; rough attaches it to a Berendes teitok.)
- DMM4162 -> e-744 (Beck+Berendes row exists but Berendes target is blank; rough attaches it to a Berendes teitok.)
- DMM4163 -> e-744 (Beck+Berendes row exists but Berendes target is blank; rough attaches it to a Berendes teitok.)

### Span-only pairs
- DMM1001 -> e-9 (Generated span assigns this Berendes entry to this Beck DMM due to missing intermediate anchors.)
- DMM1002 -> e-10 (Generated span assigns this Berendes entry to this Beck DMM due to missing intermediate anchors.)
- DMM1003 -> e-11 (Generated span assigns this Berendes entry to this Beck DMM due to missing intermediate anchors.)
- DMM1004 -> e-12 (Generated span assigns this Berendes entry to this Beck DMM due to missing intermediate anchors.)
- DMM1006 -> e-13 (Generated span assigns this Berendes entry to this Beck DMM due to missing intermediate anchors.)
- DMM1007 -> e-14 (Generated span assigns this Berendes entry to this Beck DMM due to missing intermediate anchors.)
- DMM1008 -> e-15 (Generated span assigns this Berendes entry to this Beck DMM due to missing intermediate anchors.)
- DMM1042 -> e-59 (Generated span assigns this Berendes entry to this Beck DMM due to missing intermediate anchors.)
- DMM1100 -> e-140 (Generated span assigns this Berendes entry to this Beck DMM due to missing intermediate anchors.)

## Berendes N→1 cases in rough (same teitok mapped to multiple Beck DMM ids)
- Count: 10
- e-744: DMM4161, DMM4162, DMM4163
- e-140: DMM1010, DMM1102
- e-455: DMM3040, DMM3041
- e-476: DMM3060, DMM3061
- e-493: DMM3074, DMM3075
- e-58: DMM1041, DMM1042
- e-613: DMM4031, DMM4032
- e-667: DMM4085, DMM4086
- e-715: DMM4132, DMM4133
- e-739: DMM4155, DMM4156

## Beck DMM id reuse in beck_index.csv
- Reused DMM ids: DMM1010
