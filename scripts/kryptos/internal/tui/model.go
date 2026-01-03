package tui

import (
	"fmt"
	"kryptos/internal/config"
	"kryptos/internal/generator"
	"kryptos/internal/kubeseal"
	"kryptos/pkg/utils"
	"os"
	"path/filepath"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// MainModel is the main Bubble Tea model
type MainModel struct {
	list          list.Model
	configs       []*config.AppConfig
	selected      *config.AppConfig
	currentSecret *config.Secret
	inputs        []textinput.Model
	focusIndex    int
	sealer        *kubeseal.Sealer
	quitting      bool
	width         int
	height        int
	state         viewState
}

type viewState int

const (
	viewList viewState = iota
	viewDetails
	viewForm
)

// item implements list.Item
type item struct {
	title  string
	desc   string
	config *config.AppConfig
}

func (i item) Title() string       { return i.title }
func (i item) Description() string { return i.desc }
func (i item) FilterValue() string { return i.title }

// NewModel initializes the main model
func NewModel(configs []*config.AppConfig, sealer *kubeseal.Sealer) MainModel {
	items := make([]list.Item, len(configs))
	for i, cfg := range configs {
		items[i] = item{
			title:  cfg.DisplayName,
			desc:   "Namespace: " + cfg.Namespace,
			config: cfg,
		}
	}

	d := list.NewDefaultDelegate()
	l := list.New(items, d, 0, 0)
	l.Title = "Select Application"
	l.SetShowHelp(false)

	return MainModel{
		list:    l,
		configs: configs,
		state:   viewList,
		inputs:  make([]textinput.Model, 0),
		sealer:  sealer,
	}
}

func (m MainModel) Init() tea.Cmd {
	return nil
}

func (m MainModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmd tea.Cmd

	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c", "q":
			// Only quit if not in form mode or if user consciously quits
			if m.state != viewForm {
				m.quitting = true
				return m, tea.Quit
			}
		case "enter":
			if m.state == viewList {
				i, ok := m.list.SelectedItem().(item)
				if ok {
					m.selected = i.config
					m.state = viewDetails
				}
			}
		case "esc":
			if m.state == viewDetails {
				m.state = viewList
				m.selected = nil
			} else if m.state == viewForm {
				m.state = viewDetails
				m.inputs = nil // Clear inputs
			}
		}

		// Handle secret selection in Details view
		if m.state == viewDetails {
			// Check if key is a number
			var secretIndex int
			if _, err := fmt.Sscanf(msg.String(), "%d", &secretIndex); err == nil {
				secretIndex-- // 1-based to 0-based
				if secretIndex >= 0 && secretIndex < len(m.selected.Secrets) {
					m.state = viewForm
					m.initForm(m.selected.Secrets[secretIndex])
					return m, nil
				}
			}
		}

		// Handle form navigation
		if m.state == viewForm {
			switch msg.String() {
			case "tab", "shift+tab", "enter", "up", "down":
				s := msg.String()
				if s == "enter" && m.focusIndex == len(m.inputs) {
					// Submit form
					data := make(map[string]string)
					for i, input := range m.inputs {
						val := input.Value()

						// Auto-generation logic matching original script
						var err error
						if val == "secure" {
							val, err = utils.GenerateSecurePassword(32, false)
						} else if val == "strong" {
							val, err = utils.GenerateSecurePassword(32, true)
						} else if val == "apikey" {
							val, err = utils.GenerateAPIKey(64)
						} else if val == "passphrase" {
							val = utils.GeneratePassphrase(4, "-")
						}

						if err != nil {
							// TODO: Handle error better in UI (e.g. status bar)
							// For now, print to stdout (will corrupt TUI momentarily but works for debug)
							return m, tea.Quit
						}

						data[m.currentSecret.Fields[i].Name] = val
					}

					// Generate Raw Secret
					rawSecret, err := generator.GenerateRawSecret(m.selected, *m.currentSecret, data)
					if err != nil {
						return m, tea.Quit
					}

					// Seal it
					sealedSecret, err := m.sealer.Seal(rawSecret, m.selected.Namespace, m.currentSecret.Name)
					if err != nil {
						return m, tea.Quit
					}

					// Save to file
					secretsDir, err := config.FindSecretsDir(m.selected.AppName)
					if err != nil {
						// Fallback to current dir if not found (e.g. testing)
						secretsDir = "."
						// fmt.Printf("Warning: %v. Saving to local dir.\n", err)
					}

					outputFile := filepath.Join(secretsDir, m.currentSecret.Name+".yaml")
					// If filename is customizable in config, use it (TODO)

					if err := os.WriteFile(outputFile, sealedSecret, 0644); err != nil {
						return m, tea.Quit
					}

					fmt.Printf("\nSuccessfully generated %s\n", outputFile)
					return m, tea.Quit
				}

				if s == "up" || s == "shift+tab" {
					m.focusIndex--
				} else {
					m.focusIndex++
				}

				if m.focusIndex > len(m.inputs) {
					m.focusIndex = 0
				} else if m.focusIndex < 0 {
					m.focusIndex = len(m.inputs)
				}

				cmds := make([]tea.Cmd, len(m.inputs))
				for i := 0; i <= len(m.inputs)-1; i++ {
					if i == m.focusIndex {
						// Set focused
						cmds[i] = m.inputs[i].Focus()
						m.inputs[i].PromptStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("205"))
						m.inputs[i].TextStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("205"))
					} else {
						m.inputs[i].Blur()
						m.inputs[i].PromptStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("240"))
						m.inputs[i].TextStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("240"))
					}
				}
				return m, tea.Batch(cmds...)
			}
		}

	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.list.SetWidth(msg.Width)
		m.list.SetHeight(msg.Height)
	}

	if m.state == viewList {
		m.list, cmd = m.list.Update(msg)
	}

	// Update inputs
	if m.state == viewForm {
		cmds := make([]tea.Cmd, len(m.inputs))
		for i := range m.inputs {
			m.inputs[i], cmds[i] = m.inputs[i].Update(msg)
		}
		return m, tea.Batch(cmds...)
	}

	return m, cmd
}

func (m *MainModel) initForm(secret config.Secret) {
	m.currentSecret = &secret
	m.inputs = make([]textinput.Model, len(secret.Fields))

	for i, field := range secret.Fields {
		t := textinput.New()

		// Set Prompt/Placeholder
		prompt := field.Prompt
		if prompt == "" {
			prompt = field.Name
		}
		t.Placeholder = prompt
		t.CharLimit = 1024
		t.Width = 40

		// Handle predefined values or generators
		if field.Default != "" {
			t.SetValue(field.Default)
		} else if field.Generator == "secure" {
			// Pre-generate secure password
			if val, err := utils.GenerateSecurePassword(32, false); err == nil {
				t.SetValue(val)
			}
		} else if field.Generator == "apikey" {
			if val, err := utils.GenerateAPIKey(64); err == nil {
				t.SetValue(val)
			}
		}

		// Masking for "password" fields or if generated value looks sensitive?
		// Simple heuristic: if name contains "password", "token", "secret"
		lowerName := strings.ToLower(field.Name)
		if strings.Contains(lowerName, "password") || strings.Contains(lowerName, "token") || strings.Contains(lowerName, "secret") {
			t.EchoMode = textinput.EchoPassword
			t.EchoCharacter = '•'
		}

		m.inputs[i] = t
	}
	m.focusIndex = 0
	if len(m.inputs) > 0 {
		m.inputs[0].Focus()
		m.inputs[0].PromptStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("205"))
		m.inputs[0].TextStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("205"))
	}
}

func (m MainModel) View() string {
	if m.quitting {
		return ""
	}

	if m.state == viewDetails {
		return m.viewDetails()
	}

	if m.state == viewForm {
		return m.viewForm()
	}

	return m.list.View()
}

func (m MainModel) viewDetails() string {
	if m.selected == nil {
		return "Error: No config selected"
	}

	s := lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("205")).Render("Generating Secrets for: " + m.selected.DisplayName)
	s += "\n\nAvailable Secrets:\n"

	for i, sec := range m.selected.Secrets {
		s += fmt.Sprintf("  %d. %s (%s)\n", i+1, sec.DisplayName, sec.Type)
	}

	s += "\nType the number of the secret to generate it.\n"
	s += "\nPress 'esc' to go back, 'q' to quit.\n"
	return s
}

func (m MainModel) viewForm() string {
	s := lipgloss.NewStyle().Bold(true).Render("Enter Secrets") + "\n\n"

	for i := range m.inputs {
		s += m.inputs[i].View() + "\n"
	}

	btn := lipgloss.NewStyle().Foreground(lipgloss.Color("240")).Render("[ Submit ]")
	if m.focusIndex == len(m.inputs) {
		btn = lipgloss.NewStyle().Foreground(lipgloss.Color("205")).Bold(true).Render("[ Submit ]")
	}
	s += "\n" + btn + "\n"

	return s
}
