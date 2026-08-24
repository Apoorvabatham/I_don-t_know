# Ideas — where out-of-scope ideas go to die. Writing it here is the complete response.

- Pure-Python lossless compressor (context mixing + arithmetic coding) raced vs lzma. (Phase 0
  candidate A; rejected for schedule risk. Do not resurrect mid-run.)
- Black-box optimizer shootout: DE vs SA vs CMA-lite vs random search. (Candidate C; outcome
  too predictable.)
- Add lookbehind via two-pass reverse-NFA scanning. (Violates charter NOT-doing #1. No.)
- Backreference support by falling back to the backtracker when the pattern contains \1.
  (Tempting "hybrid" scope creep. Charter NOT-doing #2. No.)
- Named groups — trivial-ish but API churn + fuzz-generator changes for zero benchmark value.
- Unicode property classes / non-ASCII corpus. (Charter NOT-doing #4.)
- Plot growth curves as PNG charts with matplotlib; interactive HTML bench report. (md+csv
  satisfies done criteria; charts are polish the freeze will not pay for.)
- Compile AST → Python source of a hand-specialized matcher per pattern ("pattern-specialized
  codegen"). Genuinely interesting, genuinely a second project. Dead.
- Memoized backtracking (packrat-style) as a third engine. Dead — M3's VM already answers the
  question; a third engine is surface area, not depth.
- Publish to PyPI / set up CI badges. (No accounts allowed anyway; charter NOT-doing #8.)
- Multithreaded Pike VM across input chunks. Breaks leftmost-first semantics; dead.
