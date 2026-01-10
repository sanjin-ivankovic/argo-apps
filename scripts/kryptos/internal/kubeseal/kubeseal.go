package kubeseal

import (
	"bytes"
	"fmt"
	"os/exec"
)

// Sealer handles interactions with the kubeseal binary
type Sealer struct {
	BinaryPath string
}

// NewSealer creates a new Sealer instance
func NewSealer() (*Sealer, error) {
	path, err := exec.LookPath("kubeseal")
	if err != nil {
		return nil, fmt.Errorf("kubeseal binary not found in PATH: %w", err)
	}
	return &Sealer{BinaryPath: path}, nil
}

// CheckConnectivity verifies if kubeseal can reach the controller
func (s *Sealer) CheckConnectivity() error {
	// kubeseal --fetch-cert is a good way to check connectivity
	cmd := exec.Command(s.BinaryPath, "--fetch-cert")
	if output, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("failed to connect to sealed-secrets controller: %v\nOutput: %s", err, string(output))
	}
	return nil
}

// Seal generates a SealedSecret from a raw K8s Secret
// input: The raw Secret YAML content
// output: The SealedSecret YAML content
func (s *Sealer) Seal(input []byte, namespace string, name string) ([]byte, error) {
	args := []string{
		"--format", "yaml",
		"--controller-namespace", "kube-system", // Default, make configurable?
		// explicitly set name and namespace to ensure they match
		"--name", name,
		"--namespace", namespace,
	}

	cmd := exec.Command(s.BinaryPath, args...)
	cmd.Stdin = bytes.NewReader(input)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("kubeseal failed: %v\nStderr: %s", err, stderr.String())
	}

	return stdout.Bytes(), nil
}
