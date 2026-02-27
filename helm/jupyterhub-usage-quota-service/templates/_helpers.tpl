{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "jupyterhub-usage-quota-service.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

# Borrowed from https://github.com/2i2c-org/binderhub-service/blob/main/binderhub-service/templates/_helpers-names.tpl
{{- /*
    Renders to a prefix for the chart's resource names. This prefix is assumed to
    make the resource name cluster unique.
*/}}
{{- define "jupyterhub-usage-quota-service.fullname" -}}
    {{- /*
        We have implemented a trick to allow a parent chart depending on this
        chart to call these named templates.

        Caveats and notes:

            1. While parent charts can reference these, grandparent charts can't.
            2. Parent charts must not use an alias for this chart.
            3. There is no failsafe workaround to above due to
               https://github.com/helm/helm/issues/9214.
            4. .Chart is of its own type (*chart.Metadata) and needs to be casted
               using "toYaml | fromYaml" in order to be able to use normal helm
               template functions on it.
    */}}
    {{- $fullname_override := .Values.fullnameOverride }}
    {{- $name_override := .Values.nameOverride }}
    {{- if ne .Chart.Name "jupyterhub-usage-quota-service" }}
        {{- if .Values.jupyterhubUsageQuotaService }}
            {{- $fullname_override = .Values.jupyterhubUsageQuotaService.fullnameOverride }}
            {{- $name_override = .Values.jupyterhubUsageQuotaService.nameOverride }}
        {{- end }}
    {{- end }}

    {{- if eq (typeOf $fullname_override) "string" }}
        {{- $fullname_override }}
    {{- else }}
        {{- $name := $name_override | default "" }}
        {{- if contains $name .Release.Name }}
            {{- .Release.Name }}
        {{- else }}
            {{- .Release.Name }}-{{ $name }}
        {{- end }}
    {{- end }}
{{- end }}


{{/*
    Renders to a blank string or if the fullname template is truthy renders to it
    with an appended dash.
*/}}
{{- define "jupyterhub-usage-quota-service.fullname.dash" -}}
    {{- if (include "jupyterhub-usage-quota-service.fullname" .) }}
        {{- include "jupyterhub-usage-quota-service.fullname" . }}-
    {{- end }}
{{- end }}

{{- /* usage-quota-service resources' default name */}}
{{- define "jupyterhub-usage-quota-service.usage-quota-service.fullname" -}}
    {{- include "jupyterhub-usage-quota-service.fullname.dash" . }}usage-quota-service
{{- end }}


{{/*
Common labels
*/}}
{{- define "jupyterhub-usage-quota-service.labels" -}}
helm.sh/chart: {{ include "jupyterhub-usage-quota-service.chart" . }}
{{ include "jupyterhub-usage-quota-service.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "jupyterhub-usage-quota-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "jupyterhub-usage-quota-service.usage-quota-service.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
