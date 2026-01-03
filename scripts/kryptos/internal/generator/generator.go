package generator

import (
	"fmt"
	"kryptos/internal/config"

	"github.com/goccy/go-yaml"
)

// K8sSecret represents a standard Kubernetes Secret
type K8sSecret struct {
	APIVersion string            `yaml:"apiVersion"`
	Kind       string            `yaml:"kind"`
	Metadata   Metadata          `yaml:"metadata"`
	Type       string            `yaml:"type"`
	StringData map[string]string `yaml:"stringData,omitempty"`
	Data       map[string]string `yaml:"data,omitempty"`
}

type Metadata struct {
	Name      string            `yaml:"name"`
	Namespace string            `yaml:"namespace"`
	Labels    map[string]string `yaml:"labels,omitempty"`
}

// GenerateRawSecret creates a Kubernetes Secret struct populated with data
func GenerateRawSecret(cfg *config.AppConfig, secretCfg config.Secret, data map[string]string) ([]byte, error) {
	// Validate required keys
	for _, field := range secretCfg.Fields {
		// Checks if the key is required
		if field.Required {
			if _, ok := data[field.Name]; !ok {
				// Check if it's in static StringData
				if _, okStr := secretCfg.StringData[field.Name]; !okStr {
					return nil, fmt.Errorf("missing required key: %s", field.Name)
				}
			}
		}
	}

	secret := K8sSecret{
		APIVersion: "v1",
		Kind:       "Secret",
		Metadata: Metadata{
			Name:      secretCfg.Name,
			Namespace: cfg.Namespace,
			Labels:    secretCfg.Labels,
		},
		Type:       "Opaque", // Default, can be overridden if needed
		StringData: data,
	}

	// Add any static StringData from config
	for k, v := range secretCfg.StringData {
		if secret.StringData == nil {
			secret.StringData = make(map[string]string)
		}
		secret.StringData[k] = v
	}

	return yaml.Marshal(secret)
}
