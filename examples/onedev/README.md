# OneDev queue with Planfile-owned GitHub publication

Set `ONEDEV_USER`, `ONEDEV_PASSWORD_FILE` and `GITHUB_TOKEN`, then run:

```bash
planfile init
planfile sync onedev --direction from
planfile sync publish onedev github
```

Doctor, Koru and other workers only need the OneDev side. Planfile stores the
cross-backend references and is the sole component that publishes Issues to
GitHub.
