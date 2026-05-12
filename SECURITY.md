# Security Policy

## Supported versions

DeltaSuite is currently in alpha. Only the latest release line receives
security fixes.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a vulnerability

If you discover a security issue in DeltaSuite, please **do not** open a
public GitHub issue. Instead:

1. Use [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
   on the repository, **or**
2. Email the maintainers at the address listed in `pyproject.toml`
   `[project].authors`.

Please include:

- A description of the issue and the impact you believe it has.
- Steps to reproduce, ideally a minimal proof of concept.
- Affected version(s) (`deltasuite --version`).
- Your operating system, Python version and any relevant kernel versions.

We will acknowledge your report within **5 business days** and aim to ship
a fix within **30 days** for high-severity issues.

## Scope

Security-relevant areas include:

- Arbitrary command execution via crafted project files (`.mdf`, `.mdu`,
  `deltasuite.toml`).
- Path traversal in project loading or kernel detection.
- Loading of malicious DLLs / shared objects from untrusted directories.
- Insecure deserialisation in settings or recent-projects storage.
- Disclosure of credentials or tokens via logs.

Issues in **third-party Delft3D kernels** (`d_hydro.exe`, `dimr.exe`,
`dflowfm.exe`, etc.) should be reported directly to
[Deltares](https://www.deltares.nl/) through their official channels.

## Out of scope

- Crashes that require a malicious user already having write access to
  the project directory.
- Issues only reproducible on EOL Python versions (< 3.11).

Thanks for helping keep DeltaSuite users safe.
