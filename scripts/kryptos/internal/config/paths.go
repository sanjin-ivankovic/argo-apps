package config

import (
	"fmt"
	"os"
	"path/filepath"
)

// FindSecretsDir locates the secrets directory for a given app
// It searches in ../../apps/{app} and ../../infrastructure/{app}
// relative to the execution root (assuming running from scripts/kryptos or similar depth)
func FindSecretsDir(appName string) (string, error) {
	// Determine Repo Root
	// Assuming CWD is inside scripts/kryptos or scripts/sealed-secrets
	// We try to find the root by looking for "apps" directory up the tree

	cwd, err := os.Getwd()
	if err != nil {
		return "", err
	}

	repoRoot := findRepoRoot(cwd)
	if repoRoot == "" {
		// Fallback: assume ../.. from current dir if "apps" not found
		// This is fragile but matches the script's assumption
		repoRoot = filepath.Join(cwd, "../..")
	}

	searchPaths := []string{
		filepath.Join(repoRoot, "apps", appName),
		filepath.Join(repoRoot, "infrastructure", appName),
	}

	var appDir string
	for _, path := range searchPaths {
		if info, err := os.Stat(path); err == nil && info.IsDir() {
			appDir = path
			break
		}
	}

	if appDir == "" {
		return "", fmt.Errorf("could not find application directory for '%s' in apps/ or infrastructure/", appName)
	}

	secretsDir := filepath.Join(appDir, "secrets")
	if err := os.MkdirAll(secretsDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create secrets directory: %w", err)
	}

	return secretsDir, nil
}

func findRepoRoot(startDir string) string {
	dir := startDir
	for {
		if _, err := os.Stat(filepath.Join(dir, "apps")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return ""
		}
		dir = parent
	}
}
