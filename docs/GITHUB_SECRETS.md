# GitHub Secrets for Automated Deployment

This document lists all GitHub secrets required for automated deployment of YuhHearDem.

**Related Documentation**:
- [deployment.md](./deployment.md) - Comprehensive deployment guide
- [DEPLOYMENT_QUICKSTART.md](./DEPLOYMENT_QUICKSTART.md) - Quick deployment guide
- [DEPLOYMENT_IMPLEMENTATION.md](./DEPLOYMENT_IMPLEMENTATION.md) - Implementation details
- [AGENTS.md](../AGENTS.md) - Comprehensive codebase guide

## Required Secrets

Set these secrets in your GitHub repository (Settings → Secrets and variables → Actions):

### SSH Connection Secrets

| Secret Name | Description | Example |
|--------------|-------------|---------|
| `YHD_HOST` | Server hostname or IP address | `89.167.28.133` or `yuhheardem.com` |
| `YHD_USER` | SSH username | `matt` |
| `YHD_PORT` | SSH port (optional, defaults to 22) | `22` |
| `YHD_SSH_KEY` | Private SSH key for authentication | `-----BEGIN OPENSSH PRIVATE KEY-----...` |

### How to Generate SSH Key

1. Generate a new SSH key pair (if you don't have one):

```bash
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions_yhd
```

2. Copy the public key to the server:

```bash
ssh-copy-id -i ~/.ssh/github_actions_yhd.pub matt@yhd
```

3. Add the private key to GitHub Secrets:

```bash
cat ~/.ssh/github_actions_yhd
```

Copy the entire output (including `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----`) to the `YHD_SSH_KEY` secret.

## Setting Up Secrets

### Via GitHub Web UI

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Enter the name and value for each secret
5. Click **Add secret**

### Via GitHub CLI

```bash
# Set secrets
gh secret set YHD_HOST -b"89.167.28.133"
gh secret set YHD_USER -b"matt"
gh secret set YHD_SSH_KEY < ~/.ssh/github_actions_yhd
```

## Verifying Secrets

### Test SSH Connection

You can verify the SSH connection works by creating a test workflow:

```yaml
name: Test SSH Connection

on:
  workflow_dispatch:

jobs:
  test-ssh:
    runs-on: ubuntu-latest
    steps:
      - name: Test SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.YHD_HOST }}
          username: ${{ secrets.YHD_USER }}
          key: ${{ secrets.YHD_SSH_KEY }}
          port: ${{ secrets.YHD_PORT || 22 }}
          script: |
            echo "SSH connection successful!"
            hostname
            whoami
```

## Security Best Practices

1. **Use strong SSH keys** (ED25519 preferred)
2. **Limit SSH access** - Use a dedicated key for GitHub Actions
3. **Rotate keys regularly** - Update secrets periodically
4. **Monitor access logs** - Check `/var/log/auth.log` on the server
5. **Use key-based auth** - Don't use passwords
6. **Restrict key usage** - Add key restrictions in `~/.ssh/authorized_keys`

## Server-Side Setup

### Add GitHub Actions Key to authorized_keys

On the server (`yhd`), ensure the GitHub Actions key is in `~/.ssh/authorized_keys`:

```bash
# On the server
cat ~/.ssh/authorized_keys
```

You should see the public key that corresponds to `YHD_SSH_KEY`.

### Restrict Key Usage (Optional)

For better security, you can restrict the GitHub Actions key to only run deployment commands:

```bash
# On the server, add this before the GitHub Actions key in authorized_keys:
command="cd /opt/yuhheardem && $SHELL",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty
```

This ensures the key can only be used for deployment purposes.

## Troubleshooting

### SSH Connection Fails

1. Verify the secret is correctly set:

```bash
gh secret list
```

2. Check server firewall allows SSH:

```bash
# On the server
sudo ufw status
sudo ufw allow 22/tcp
```

3. Verify key format - must be in OpenSSH format:

```bash
# Check key format
head -1 ~/.ssh/github_actions_yhd
# Should output: -----BEGIN OPENSSH PRIVATE KEY-----
```

### Permission Denied

1. Check file permissions on server:

```bash
ls -la ~/.ssh/authorized_keys
# Should be: -rw------- (600)
```

2. Fix permissions if needed:

```bash
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

### Deployment Fails

Check the GitHub Actions logs for detailed error messages. Common issues:

- **Wrong user**: Verify `YHD_USER` matches the user on the server
- **Wrong host**: Verify `YHD_HOST` is correct
- **Key format**: Ensure `YHD_SSH_KEY` is in OpenSSH format
- **Server unreachable**: Check server is online and accessible

## Additional Resources

- [GitHub Actions Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [SSH Key Best Practices](https://www.ssh.com/academy/ssh/key)
- [Deployment Documentation](./deployment.md)
- [Deployment Quickstart](./DEPLOYMENT_QUICKSTART.md)

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [AGENTS.md](../AGENTS.md) | Comprehensive codebase guide with code map |
| [README.md](../README.md) | Project overview and quick start |
| [deployment.md](./deployment.md) | Comprehensive deployment guide |
| [DEPLOYMENT_QUICKSTART.md](./DEPLOYMENT_QUICKSTART.md) | Quick deployment reference |
| [DEPLOYMENT_IMPLEMENTATION.md](./DEPLOYMENT_IMPLEMENTATION.md) | Implementation details |
| [ARCHITECTURE_ANALYSIS.md](./ARCHITECTURE_ANALYSIS.md) | System architecture analysis |
| [REBUILD_PLAN.md](./REBUILD_PLAN.md) | Original implementation plan |
