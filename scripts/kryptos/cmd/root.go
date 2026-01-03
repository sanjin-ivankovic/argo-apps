package cmd

import (
	"fmt"
	"kryptos/internal/config"
	"kryptos/internal/kubeseal"
	"kryptos/internal/tui"
	"os"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "kryptos",
	Short: "Kryptos - Interactive SealedSecret Generator",
	Long: `Kryptos is an enterprise-grade CLI tool for generating Kubernetes SealedSecrets.
It provides a rich interactive interface for managing secrets across multiple applications.`,
	Run: func(cmd *cobra.Command, args []string) {
		// Load Configs
		configDir := "configs"
		files, err := config.ListConfigs(configDir)
		if err != nil {
			fmt.Printf("Error listing configs from %s: %v\n", configDir, err)
			os.Exit(1)
		}

		var appConfigs []*config.AppConfig
		for _, f := range files {
			cfg, err := config.LoadConfig(f)
			if err != nil {
				fmt.Printf("Warning: Could not load %s: %v\n", f, err)
				continue
			}
			appConfigs = append(appConfigs, cfg)
		}

		if len(appConfigs) == 0 {
			fmt.Println("No valid configurations found.")
			os.Exit(1)
		}

		// Initialize Kubeseal
		sealer, err := kubeseal.NewSealer()
		if err != nil {
			fmt.Printf("Error initializing kubeseal: %v\n", err)
			os.Exit(1)
		}

		// Check connectivity (optional, warn on failure)
		if err := sealer.CheckConnectivity(); err != nil {
			fmt.Printf("Warning: Could not connect to sealed-secrets controller: %v\n", err)
			fmt.Println("Proceeding anyway (offline sealing might fail if cert not cached)...")
		}

		// Start TUI
		p := tea.NewProgram(tui.NewModel(appConfigs, sealer), tea.WithAltScreen())
		if _, err := p.Run(); err != nil {
			fmt.Printf("Alas, there's been an error: %v", err)
			os.Exit(1)
		}
	},
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}

func init() {
	// Global flags can be defined here
}
