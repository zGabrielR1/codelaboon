# Latest release candidate: 1.0.0rc13

RC13 makes `codelaboon claude` use Codelaboon free providers with no Claude account
or subscription. Native onboarding is prepared automatically; the model picker
lists the free catalogue, and native tools/streaming use the loopback adapter.
See [RC13 notes](release-1.0.0rc13.md) and [review](review-1.0.0rc13.md).

Validated locally: 191 tests, native Claude UI/model picker and file-tool loop
without Anthropic credentials, and a live free-provider reply. OpenCode stays the
default and retains the RC12 startup fix confirmed by the user in Ptyxis.

Publication requires successful `v1.0.0-rc.13` CI, including native Claude tests
and the existing OpenCode/OMP/Kilo/VTE gates. Free-provider quotas still apply.
