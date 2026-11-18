{#
    Les fichiers Open DAMIR sont chargés en STRING dans la zone brute.
    Ces macros centralisent le nettoyage pour qu'il soit identique partout.
#}

{# Montant ou indicateur numérique : gère la virgule décimale, les espaces et les vides. #}
{% macro parse_number(column) -%}
    safe_cast(replace(replace(nullif(trim({{ column }}), ''), ' ', ''), ',', '.') as numeric)
{%- endmacro %}

{# Code de nomenclature : retire les espaces et un éventuel suffixe ".0" (export tableur). #}
{% macro clean_code(column) -%}
    nullif(regexp_replace(trim({{ column }}), r'\.0+$', ''), '')
{%- endmacro %}

{# Code entier normalisé en texte ("011" -> "11") pour les jointures avec les seeds. #}
{% macro clean_int_code(column) -%}
    cast(safe_cast({{ clean_code(column) }} as int64) as string)
{%- endmacro %}
