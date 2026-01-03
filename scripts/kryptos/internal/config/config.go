package config

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/goccy/go-yaml"
)

// Internal definitions (Used by the application)

type AppConfig struct {
	AppName     string
	DisplayName string
	Namespace   string
	Destination string
	Secrets     []Secret
}

type Secret struct {
	Name        string
	DisplayName string
	Type        string
	Description string
	Filename    string
	Fields      []SecretField // Unified list of fields
	Labels      map[string]string
	StringData  map[string]string
}

type SecretField struct {
	Name      string
	Prompt    string
	Required  bool
	Generator string
	Default   string
	Length    int
}

// V1 Schema Definitions

type kv1AppConfig struct {
	APIVersion string      `yaml:"apiVersion"`
	Kind       string      `yaml:"kind"`
	Metadata   kv1Metadata `yaml:"metadata"`
	Spec       kv1Spec     `yaml:"spec"`
}

type kv1Metadata struct {
	Name        string `yaml:"name"`
	DisplayName string `yaml:"displayName"`
	Namespace   string `yaml:"namespace"`
}

type kv1Spec struct {
	Secrets []kv1Secret `yaml:"secrets"`
}

type kv1Secret struct {
	Name        string            `yaml:"name"`
	DisplayName string            `yaml:"displayName"`
	Description string            `yaml:"description"`
	Type        string            `yaml:"type"`
	Fields      []kv1Field        `yaml:"fields"`
	StringData  map[string]string `yaml:"stringData"`
	Labels      map[string]string `yaml:"labels"`
}

type kv1Field struct {
	Name      string `yaml:"name"`
	Prompt    string `yaml:"prompt"`
	Required  bool   `yaml:"required"`
	Generator string `yaml:"generator"`
	Default   string `yaml:"default"`
	Length    int    `yaml:"length"`
}

// Legacy Schema Definitions

type legacyAppConfig struct {
	AppName     string         `yaml:"app_name"`
	DisplayName string         `yaml:"display_name"`
	Namespace   string         `yaml:"namespace"`
	Secrets     []legacySecret `yaml:"secrets"`
}

type legacySecret struct {
	Name        string            `yaml:"name"`
	DisplayName string            `yaml:"display_name"`
	Type        string            `yaml:"type"`
	Description string            `yaml:"description"`
	Keys        []string          `yaml:"keys"`
	StringData  map[string]string `yaml:"stringData"`
	Labels      map[string]string `yaml:"labels"`
}

// LoadConfig reads a YAML configuration file and returns a unified AppConfig
func LoadConfig(path string) (*AppConfig, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("error reading config file: %w", err)
	}

	// 1. Try mapping the API Version
	var header struct {
		APIVersion string `yaml:"apiVersion"`
	}
	if err := yaml.Unmarshal(data, &header); err == nil && header.APIVersion == "kryptos.dev/v1" {
		return loadV1Config(data)
	}

	// 2. Fallback to Legacy
	return loadLegacyConfig(data)
}

func loadV1Config(data []byte) (*AppConfig, error) {
	var v1 kv1AppConfig
	if err := yaml.Unmarshal(data, &v1); err != nil {
		return nil, fmt.Errorf("error parsing v1 config: %w", err)
	}

	app := &AppConfig{
		AppName:     v1.Metadata.Name,
		DisplayName: v1.Metadata.DisplayName,
		Namespace:   v1.Metadata.Namespace,
	}

	for _, s := range v1.Spec.Secrets {
		secret := Secret{
			Name:        s.Name,
			DisplayName: s.DisplayName,
			Type:        s.Type,
			Description: s.Description,
			Labels:      s.Labels,
			StringData:  s.StringData,
		}
		for _, f := range s.Fields {
			secret.Fields = append(secret.Fields, SecretField{
				Name:      f.Name,
				Prompt:    f.Prompt,
				Required:  f.Required,
				Generator: f.Generator,
				Default:   f.Default,
				Length:    f.Length,
			})
		}
		app.Secrets = append(app.Secrets, secret)
	}
	return app, nil
}

func loadLegacyConfig(data []byte) (*AppConfig, error) {
	var legacy legacyAppConfig
	if err := yaml.Unmarshal(data, &legacy); err != nil {
		return nil, fmt.Errorf("error parsing legacy config: %w", err)
	}

	app := &AppConfig{
		AppName:     legacy.AppName,
		DisplayName: legacy.DisplayName,
		Namespace:   legacy.Namespace,
	}

	for _, s := range legacy.Secrets {
		secret := Secret{
			Name:        s.Name,
			DisplayName: s.DisplayName,
			Type:        s.Type,
			Description: s.Description,
			Labels:      s.Labels,
			StringData:  s.StringData,
		}
		// Convert string keys to Fields
		for _, k := range s.Keys {
			secret.Fields = append(secret.Fields, SecretField{
				Name:   k,
				Prompt: k, // Default prompt is the key name
			})
		}
		app.Secrets = append(app.Secrets, secret)
	}
	return app, nil
}

// ListConfigs finds all YAML configs in the given directory
func ListConfigs(dir string) ([]string, error) {
	files, err := filepath.Glob(filepath.Join(dir, "*.yaml"))
	if err != nil {
		return nil, err
	}
	return files, nil
}
