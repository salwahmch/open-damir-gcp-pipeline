{#
    Mode « BigQuery sandbox » (projet sans compte de facturation), activé par
    BQ_SANDBOX=true (valeur par défaut). Le sandbox n'accepte pas le DML
    (MERGE, INSERT, DELETE) et supprime automatiquement les tables et partitions
    de plus de 60 jours. On n'y utilise donc ni modèle incrémental, ni partition
    datée par mois de traitement (une partition de 2024 expirerait aussitôt).
#}
{% macro is_sandbox() -%}
    {{ return(env_var('BQ_SANDBOX', 'true') | trim | lower in ['true', '1', 'yes', 'oui', 'on']) }}
{%- endmacro %}
