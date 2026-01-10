package utils

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"math/big"
	"strings"
)

const (
	defaultPasswordLength = 32
	minPasswordLength     = 8
	apiKeyLength          = 64
)

// GenerateSecurePassword generates a strong password with mixed character sets
func GenerateSecurePassword(length int, includeSymbols bool) (string, error) {
	if length < minPasswordLength {
		length = minPasswordLength
	}

	lower := "abcdefghjkmnpqrstuvwxyz"
	upper := "ABCDEFGHJKMNPQRSTUVWXYZ"
	digits := "23456789" // Avoid confusing 0/1 with O/I
	symbols := "!@#$%^&*"

	allChars := lower + upper + digits
	if includeSymbols {
		allChars += symbols
	}

	buf := make([]byte, length)

	// Ensure at least one of each required type
	buf[0] = lower[mustRandInt(len(lower))]
	buf[1] = upper[mustRandInt(len(upper))]
	buf[2] = digits[mustRandInt(len(digits))]
	nextIdx := 3

	if includeSymbols {
		buf[3] = symbols[mustRandInt(len(symbols))]
		nextIdx = 4
	}

	// Fill the rest randomly
	for i := nextIdx; i < length; i++ {
		buf[i] = allChars[mustRandInt(len(allChars))]
	}

	// Shuffle the result
	perm, err := randPerm(length)
	if err != nil {
		return "", err
	}

	shuffled := make([]byte, length)
	for i, idx := range perm {
		shuffled[i] = buf[idx]
	}

	return string(shuffled), nil
}

// GenerateAPIKey generates a hex-encoded random API key
func GenerateAPIKey(length int) (string, error) {
	bytes := make([]byte, length/2) // 2 hex chars per byte
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes), nil
}

// GenerateBase64Key generates a base64 encoded strong random key
func GenerateBase64Key(length int) (string, error) {
	bytes := make([]byte, length)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return base64.StdEncoding.EncodeToString(bytes), nil
}

// GeneratePassphrase generates a word-based passphrase
func GeneratePassphrase(wordCount int, separator string) string {
	words := []string{
		"apple", "banana", "cherry", "dragon", "eagle", "forest", "garden", "harbor",
		"island", "jungle", "kettle", "lemon", "mountain", "night", "ocean", "palace",
		"queen", "river", "sunset", "tiger", "umbrella", "village", "winter", "yellow",
		"zebra", "anchor", "bridge", "castle", "desert", "emerald", "falcon", "glacier",
	}

	selected := make([]string, wordCount)
	for i := 0; i < wordCount; i++ {
		selected[i] = words[mustRandInt(len(words))]
	}

	return strings.Join(selected, separator)
}

// Helper: randInt returns a secure random integer [0, max)
func randInt(max int) (int, error) {
	n, err := rand.Int(rand.Reader, big.NewInt(int64(max)))
	if err != nil {
		return 0, err
	}
	return int(n.Int64()), nil
}

func mustRandInt(max int) int {
	val, err := randInt(max)
	if err != nil {
		panic(err) // Should not happen in normal operation
	}
	return val
}

func randPerm(n int) ([]int, error) {
	// There is no crypto/rand.Perm, implement Fisher-Yates shuffle if strict needed
	// For simplicity, we can use a basic shuffle here or just rely on random generation filling

	// Using a slice and random swaps
	indices := make([]int, n)
	for i := 0; i < n; i++ {
		indices[i] = i
	}

	for i := n - 1; i > 0; i-- {
		j, err := randInt(i + 1)
		if err != nil {
			return nil, err
		}
		indices[i], indices[j] = indices[j], indices[i]
	}

	return indices, nil
}
