# item 8: load-bearing audit of the checks added by the eighth remediation

Method: the shadow gate is imported and one check is replaced by a permissive stub, then the
gate's own 49-control sweep and its 12 benign probes are re-run. A check is load-bearing for the
red side only if a built-in control slips; load-bearing for the green side only if a benign probe
breaks.

| check replaced by a permissive stub | built-in controls | benign probes |
| --- | --- | --- |
| `guard_is_reachable depth-1 rule` | CONTROL SLIPPED -> negative control guard-call-moved-to-dead-method was accepted; the guard is ineffective | all 12 benign probes still accepted |
| `mask_literals inside bean_bodies` | all 49 controls still rejected | BENIGN BROKEN -> code: verifySessionCookieContract(env) is not a direct statement of an assembled @Bean body |
| `decode_unicode_escapes` | CONTROL SLIPPED -> negative control guard-call-under-escaped-line-comment was accepted; the guard is ineffective | all 12 benign probes still accepted |
| `live_pattern / in_literal` | all 49 controls still rejected | all 12 benign probes still accepted |
| `expand_flow in cookie_names` | CONTROL SLIPPED -> negative control flow-profile-override-cookie-name was accepted; the guard is ineffective | all 12 benign probes still accepted |
| `GUARD_TEST_REQUIRE per-body needles` | all 49 controls still rejected | all 12 benign probes still accepted |
| `method_span` | all 49 controls still rejected | all 12 benign probes still accepted |
| `depth_at` | CONTROL SLIPPED -> negative control guard-call-in-constant-false-branch was accepted; the guard is ineffective | all 12 benign probes still accepted |
| `binding_inputs profile coverage` | CONTROL SLIPPED -> 'guardTestXml' | BENIGN BROKEN -> 'guardTestXml' |
| `CI_GATE_NEEDLE specificity` | all 49 controls still rejected | all 12 benign probes still accepted |

extra isolation runs (item8b):
- with the profile config files removed from `binding_inputs`, `binding-profile-stale` slips:
  the profile coverage is load-bearing.
- with `live_pattern` made blind to literals, all 49 controls still reject, yet a hand-made
  mutant that keeps the secure clause only as text-block prose is ACCEPTed: the dimension is
  real and uncontrolled.

