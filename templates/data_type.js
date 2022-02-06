fs = require("fs")
{% if object_var %}
let {{ object_var[0] }} = {}
{{ object_var[0] }}.{{ object_var[1] }} = function(self, key, val) { self[key] = val; }
{% endif %}
{{ data }}
for (let {{ data_type[0] }} in {{ data_type }}) {
    if (typeof {{ data_type }}[{{ data_type[0] }}].getTooltip === "function") {
        {{ data_type }}[{{ data_type[0] }}].tooltip = {{ data_type }}[{{ data_type[0] }}].getTooltip({{ data_type }}[{{ data_type[0] }}].strengthPerLevel, 1);
    }
}

fs.writeFileSync("{{ json_file }}", JSON.stringify({{ data_type }}), "utf-8")