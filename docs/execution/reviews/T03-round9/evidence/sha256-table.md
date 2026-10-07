# sha256 of the bytes this verdict binds to

captured at HEAD fb622124e3b461e7899abd55a72d159d9d00f7ee (git status dirty files listed at the bottom)

| file | sha256 |
| --- | --- |
| `record` = `092796323f3e463cddcdd184b7629d63e3189259d92c756f0564570ddf7e933b` | `092796323f3e463cddcdd184b7629d63e3189259d92c756f0564570ddf7e933b` |
| `bindingJson` = `2c674ccc68940f9c087db3404e17771c51a77f1fc514bee04692e25bd9212d12` | `2c674ccc68940f9c087db3404e17771c51a77f1fc514bee04692e25bd9212d12` |
| `ci` = `2f651cb7ba7b429bbd14b55fc70d74bdfa324ee9a20c0b7bf6738194e76693d8` | `2f651cb7ba7b429bbd14b55fc70d74bdfa324ee9a20c0b7bf6738194e76693d8` |
| `config-application-dev.yml` = `41ee5e1caae10f1351f2c156bd290b60f9a66b9c4a322a2b43555625fd656b68` | `41ee5e1caae10f1351f2c156bd290b60f9a66b9c4a322a2b43555625fd656b68` |
| `config-application.yml` = `42acb38562eb3212b1c66d9875c6f8ab12deca48576d77e0214289151cc1d06d` | `42acb38562eb3212b1c66d9875c6f8ab12deca48576d77e0214289151cc1d06d` |
| `guardTest` = `7ba45cc489bf674ab33a227b6e9a25190491499a1961047d439732eeea465246` | `7ba45cc489bf674ab33a227b6e9a25190491499a1961047d439732eeea465246` |
| `gate` = `a86f64dd3f59d9306628023dd228c2b51569adac467d6ae27229b1d92005970c` | `a86f64dd3f59d9306628023dd228c2b51569adac467d6ae27229b1d92005970c` |
| `config-application-prod.yml` = `bb769d087a85807a88b8aaca5c017553527ca086abb6fc6dc6f443904a6ee0a0` | `bb769d087a85807a88b8aaca5c017553527ca086abb6fc6dc6f443904a6ee0a0` |
| `code` = `bda8f72167fc1a4634a414af16843c22f9258edda4180ccf3473f8a97a5eee44` | `bda8f72167fc1a4634a414af16843c22f9258edda4180ccf3473f8a97a5eee44` |
| `config-application-mock.yml` = `c39f099652737792cc8106d6b121ab7c98a47f706976f2374bd23cbe8c44efe8` | `c39f099652737792cc8106d6b121ab7c98a47f706976f2374bd23cbe8c44efe8` |
| `surefireXml` = `d101e511311bf8dcd5aab670d1e426df77a0b17eca3521d32ea0cbe7211f7306` | `d101e511311bf8dcd5aab670d1e426df77a0b17eca3521d32ea0cbe7211f7306` |

gate sha256 printed inside its own JSON output: `a86f64dd3f59d9306628023dd228c2b51569adac467d6ae27229b1d92005970c`
reviewed claim was prefix a86f64dd3f59; re-verified match: True

self-run gate: exit 0, negativeControlCount 49, benignProbeCount 12, bound inputs 8, configs 4

check_contracts.py: exit 0 :: Approved T00 rc.3: 27 hashes verified, no regeneration

dirty working files (belong to the two other live sessions, not this review):

- `M docs/execution/reports/T08-Revision-R3.md`
- ` M docs/execution/reports/T08.md`
- `?? .tmp_t08fix.py`
- `?? docs/execution/reviews/T02-round4/`
- `?? docs/execution/reviews/T03-round9/`
re-check at the newest HEAD 9f1df7e (the repo kept advancing while this review ran; the two other live
sessions commit to T02/T08 paths only): every byte this verdict binds to is unchanged --
check_session_cookie.py a86f64dd3f59d930, T03Configuration.java bda8f72167fc1a46,
T03SessionCookieGuardTest.java 7ba45cc489bf674a, guard-test-binding.json 2c674ccc68940f9c,
T03SessionCookieGuardTest.xml d101e511311bf8dc, record_guard_binding.py 092796323f3e463c,
application.yml 42acb38562eb3212, application-prod.yml bb769d087a85807a, ci.yml 2f651cb7ba7b429b.
A fresh gate run at that HEAD (output written outside the repo, then deleted) still reported
verdict PASS, negativeControlCount 49, benignProbeCount 12, boundInputs 8, configFilesScanned 4,
ci 2f651cb7... and bindingLabel 'binding' with surefireXmlCrossChecked true.
