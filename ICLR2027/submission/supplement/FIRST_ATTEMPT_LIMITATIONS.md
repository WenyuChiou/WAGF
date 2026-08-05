# First-attempt and retry limitation

The frozen audit record stores the final proposed action for the primary
analysis and a validation message when a response is rejected. It does not
store the first agent report before the retry that produced the accepted final
response.

Therefore this package cannot separate:

1. a within-decision revision of the reported condition after feedback; and
2. selection into the set of final accepted records.

Figure 1 therefore omits a retry endpoint rather than implying that the first
attempt is observed. The manuscript's reporting protocol recommends storing
the first response, the validation message, and the final response as separate
records in future runs.
