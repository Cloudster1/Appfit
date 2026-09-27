{{/* Names */}}
{{- define "appfit.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "appfit.fullname" -}}
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

{{/* Name of a component resource, e.g. appfit.component (dict "root" . "name" "backend") */}}
{{- define "appfit.component" -}}
{{- printf "%s-%s" (include "appfit.fullname" .root) .name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Labels */}}
{{- define "appfit.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "appfit.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: appfit
{{- end }}

{{- define "appfit.selectorLabels" -}}
app.kubernetes.io/name: {{ include "appfit.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* Labels of one component: include "appfit.componentLabels" (dict "root" . "component" "backend") */}}
{{- define "appfit.componentLabels" -}}
{{ include "appfit.labels" .root }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{- define "appfit.componentSelectorLabels" -}}
{{ include "appfit.selectorLabels" .root }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{- define "appfit.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "appfit.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/* Images */}}
{{- define "appfit.image" -}}
{{- printf "%s:%s" .image.repository (default .root.Chart.AppVersion .image.tag) }}
{{- end }}

{{/* Secrets: a value given in values, else the one already in the cluster, else a new random one. */}}
{{- define "appfit.secretValue" -}}
{{- $existing := lookup "v1" "Secret" .root.Release.Namespace .secret }}
{{- if .value }}
{{- .value }}
{{- else if and $existing (hasKey $existing.data .key) }}
{{- index $existing.data .key | b64dec }}
{{- else }}
{{- randAlphaNum 32 }}
{{- end }}
{{- end }}

{{- define "appfit.appSecretName" -}}
{{- default (include "appfit.component" (dict "root" . "name" "auth")) .Values.auth.existingSecret }}
{{- end }}

{{- define "appfit.postgresql.host" -}}
{{- include "appfit.component" (dict "root" . "name" "postgresql") }}
{{- end }}

{{- define "appfit.postgresql.secretName" -}}
{{- default (include "appfit.component" (dict "root" . "name" "postgresql")) .Values.postgresql.auth.existingSecret }}
{{- end }}

{{/* External databases: the Secret and key holding DATABASE_URL. */}}
{{- define "appfit.databaseSecretName" -}}
{{- default (include "appfit.component" (dict "root" . "name" "database")) .Values.externalDatabase.existingSecret }}
{{- end }}

{{- define "appfit.databaseSecretKey" -}}
{{- if .Values.externalDatabase.existingSecret }}
{{- .Values.externalDatabase.existingSecretKey }}
{{- else }}
{{- "DATABASE_URL" }}
{{- end }}
{{- end }}

{{- define "appfit.cookieSecure" -}}
{{- if ne (toString .Values.config.cookieSecure) "" }}
{{- .Values.config.cookieSecure | toString }}
{{- else }}
{{- and .Values.ingress.enabled (gt (len .Values.ingress.tls) 0) | toString }}
{{- end }}
{{- end }}

{{/* The model cache is shared by API and worker pods. */}}
{{- define "appfit.modelCacheClaim" -}}
{{- default (include "appfit.component" (dict "root" . "name" "model-cache")) .Values.modelCache.persistence.existingClaim }}
{{- end }}

{{- define "appfit.modelCacheIsRWO" -}}
{{- if and .Values.modelCache.persistence.enabled (not (has "ReadWriteMany" .Values.modelCache.persistence.accessModes)) }}true{{- end }}
{{- end }}

{{/* Env shared by API and worker containers. */}}
{{- define "appfit.backendEnv" -}}
{{- if .Values.postgresql.enabled }}
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "appfit.postgresql.secretName" . }}
      key: POSTGRES_PASSWORD
# Kubernetes fills in $(POSTGRES_PASSWORD); it must be URL-safe (the generated one is).
- name: DATABASE_URL
  value: {{ printf "postgresql+psycopg://%s:$(POSTGRES_PASSWORD)@%s:5432/%s" .Values.postgresql.auth.username (include "appfit.postgresql.host" .) .Values.postgresql.auth.database | quote }}
{{- else }}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "appfit.databaseSecretName" . }}
      key: {{ include "appfit.databaseSecretKey" . }}
{{- end }}
- name: JWT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ include "appfit.appSecretName" . }}
      key: JWT_SECRET
- name: BOOTSTRAP_ADMIN_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "appfit.appSecretName" . }}
      key: BOOTSTRAP_ADMIN_PASSWORD
{{- end }}

{{- define "appfit.backendVolumes" -}}
- name: model-cache
{{- if .Values.modelCache.persistence.enabled }}
  persistentVolumeClaim:
    claimName: {{ include "appfit.modelCacheClaim" . }}
{{- else }}
  emptyDir: {}
{{- end }}
- name: tmp
  emptyDir: {}
- name: home-cache
  emptyDir: {}
{{- end }}

{{- define "appfit.backendVolumeMounts" -}}
- name: model-cache
  mountPath: /models
- name: tmp
  mountPath: /tmp
- name: home-cache
  mountPath: /home/appfit/.cache
{{- end }}

{{/* Pod security context of API and worker pods: the image's appfit user, which must own the model cache. */}}
{{- define "appfit.backendPodSecurityContext" -}}
{{- $ids := dict "runAsUser" 10001 "runAsGroup" 10001 "fsGroup" 10001 "fsGroupChangePolicy" "OnRootMismatch" }}
{{- toYaml (merge (deepCopy .Values.podSecurityContext) $ids) }}
{{- end }}
