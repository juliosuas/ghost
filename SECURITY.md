# Security Policy

## Supported versions

Only the **latest release** of Ghost receives security fixes. Older releases are not supported and will not be patched or backported.

There is no tagged release yet. Until the first release is published, only the `main` branch is supported.

## Reporting a vulnerability

Report vulnerabilities privately through GitHub Private Vulnerability Reporting:

1. Open the **Security** tab of this repository.
2. Choose **Report a vulnerability**.
3. Submit the report there.

Do not open a public GitHub issue, discussion, or pull request for an unfixed vulnerability, and do not post exploit details in public until a fix is released.

**Initial response:** we will acknowledge a report within **7 days**.

Please include the affected version or commit, the impact, and steps to reproduce. A suggested fix is welcome but not required.

## Scope

**In scope**

- The Ghost application in this repository (CLI, local Flask server, case storage, modules, and report generation)
- Workflows and other repository configuration under `.github/`
- The Docker image built from this repository and release artifacts published from it

**Out of scope**

- Third-party sites, APIs, and data sources that Ghost queries
- Vulnerabilities in dependencies with no demonstrated impact on Ghost (report those to the upstream project; a private note is still welcome if Ghost is affected)
- Social engineering, physical attacks, and denial of service
- Findings that require using Ghost against a target without authorization

## Safe harbor

We consider security research conducted in good faith to be authorized, and we will not pursue legal action against researchers who follow this policy.

Good-faith research means you:

- Report through GitHub Private Vulnerability Reporting and give us a reasonable time to investigate and fix the issue before any public disclosure
- Avoid privacy violations, data destruction, and degradation of service
- Do not access, modify, or exfiltrate data that is not yours beyond the minimum needed to demonstrate the issue
- Do not exploit a vulnerability beyond the minimum proof required

This safe harbor applies to good-faith research covered by this policy. It does not cover activity that is not in good faith.
