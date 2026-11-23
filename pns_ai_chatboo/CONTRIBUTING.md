# Contributing

This repository is generated from our internal tree on every release. Pull requests are switched off: a merge here would be overwritten by the next release.

| You have | Where it goes |
| :--- | :--- |
| A bug | An issue, with the bug form |
| An idea or a question | Discussions |
| A security problem | A private report, see [SECURITY.md](SECURITY.md) |

If we take your idea, we implement it internally and credit you in the release notes. Do not paste secrets, API keys or customer data anywhere.

The code is Apache-2.0: you are free to fork it and keep your changes.
## If you fork

Chatboo owns the conversation UI. Inference, providers and Safe Plan stay
in `pns_ai_mcp`. Do not re-implement the engine here.
