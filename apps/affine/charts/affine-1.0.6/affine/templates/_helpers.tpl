{{/*
Expand the name of the chart.
*/}}
{{- define "affine.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "affine.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "affine.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "affine.labels" -}}
helm.sh/chart: {{ include "affine.chart" . }}
{{ include "affine.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "affine.selectorLabels" -}}
app.kubernetes.io/name: {{ include "affine.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the PVC for a given volume
*/}}
{{- define "affine.pvcName" -}}
{{- printf "%s-%s" (include "affine.fullname" .) .volumeName }}
{{- end }}

{{/*
Generate the DATABASE_URL environment variable
*/}}
{{- define "affine.databaseUrl" -}}
{{- if eq .Values.database.type "external" -}}
postgresql://{{ .Values.database.username }}:$(DB_PASSWORD)@{{ .Values.database.host }}:{{ .Values.database.port }}/{{ .Values.database.name }}
{{- else -}}
postgresql://{{ .Values.database.username }}:$(DB_PASSWORD)@postgres:5432/{{ .Values.database.name }}
{{- end -}}
{{- end }}

{{/*
Generate the Redis host
*/}}
{{- define "affine.redisHost" -}}
{{- if eq .Values.redis.type "external" -}}
{{- .Values.redis.host }}
{{- else -}}
redis
{{- end -}}
{{- end }}

{{/*
Generate the external URL for AFFiNE
*/}}
{{- define "affine.externalUrl" -}}
{{- if .Values.affine.server.externalUrl -}}
{{- .Values.affine.server.externalUrl }}
{{- else -}}
{{- if .Values.affine.server.https -}}
https://{{ .Values.affine.server.host }}
{{- else -}}
http://{{ .Values.affine.server.host }}
{{- end -}}
{{- end -}}
{{- end }}
