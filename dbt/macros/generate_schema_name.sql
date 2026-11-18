{#
    Par défaut dbt préfixe les schémas personnalisés par le dataset cible
    (ex. damir_damir_marts). On utilise directement le nom personnalisé
    pour obtenir des datasets lisibles : damir_staging, damir_marts, damir_ref.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
