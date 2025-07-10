import re

def get_unit_template():

    base_unit = r"\{?\\mathrm\s*\{[^}]*?\}\}?\}?"
    super_sub = r"(?:\s*\\?[\^\^]\s*(?:\{[^}]*?\}|[^{}\s]+))?"
    pattern1 = rf"({base_unit}{super_sub})"
    connector = r"(?:\\cdot|/|\\times)"
    pattern2 = rf"((?:{base_unit}{super_sub}\s*{connector}?\s*)+)"
    bracketed = r"\\left(\\\{)?[^()]*?\\right(\\\})?"
    pattern3 = rf"({bracketed}\s*{super_sub})"
    pattern4 = rf"(\^{{[^}}\d]*?}}\s*{base_unit})"
    pattern5 = r"(\^\{?\s*\\[a-zA-Z]+\b\}?)"

    master_pattern = re.compile(
        rf"{pattern2}|{pattern3}|{pattern4}|{pattern1}|{pattern5}"
    )

    return master_pattern

class EnhancedVariableExtractor:
    def __init__(self, text, exp_need=True):
        self.original_text = text
        self.param_values = {}
        self.param_ids = []
        self.template = ""
        self.matches = []
        self.exp_need = exp_need
        self.forbidden_zones = []
        self._extract_numbers()
        self._generate_template()

    def _overlaps_forbidden(self, start, end):
        for zone in self.forbidden_zones:
            z_start, z_end = zone
            if start < z_end and end > z_start:
                return True
        return False

    def _add_forbidden_zone(self, start, end):
        self.forbidden_zones.append((start, end))
        self.forbidden_zones.sort(key=lambda x: x[0])
        merged = []
        for start, end in self.forbidden_zones:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        self.forbidden_zones = merged

    def _extract_numbers(self):
        subscript_pattern = r'_\s*{[^}]*}'
        for match in re.finditer(subscript_pattern, self.original_text):
            self._add_forbidden_zone(match.start(), match.end())
        unit_pattern = get_unit_template()
        for match in re.finditer(unit_pattern, self.original_text):
            self._add_forbidden_zone(match.start(), match.end())

        self._extract_scientific_notation()

        superscript_pattern = r'\^\s*\{?[^}]*\}?'
        for match in re.finditer(superscript_pattern, self.original_text):
            self._add_forbidden_zone(match.start(), match.end())

        braced_pattern = r'([-+]?\s*\{?\d+(?:\.\d+)?\s*\}?)'
        for match in re.finditer(braced_pattern, self.original_text):
            start, end = match.span()
            if not self._overlaps_forbidden(start, end):
                value = match.group(1)
                value = re.sub(r'\{|\}', '', value)
                self.matches.append((start, end, value))
                self._add_forbidden_zone(start, end)

        standalone_pattern = r'(?<!\w)([-+]?\s*\d+(?:\.\d+)?)(?=[^\w]|$)'
        for match in re.finditer(standalone_pattern, self.original_text):
            start, end = match.span()
            value_str = match.group(0)
            if not self._overlaps_forbidden(start, end):
                value = value_str
                self.matches.append((start, end, value))
                self._add_forbidden_zone(start, end)


    def _extract_scientific_notation(self):
        sci_pattern_list = [
            r'\{?\s*([-+]?\s*[\d\.]+)\s*\}?\s*(?:\*|×|\\times|\\cdot|x|X)\s*\{?10\}?\s*\^\s*\{?\s*([-+]?\s*\{?\d+\}?)\s*\}?',
            r'([-+]?\s*[\d\.]+)\s*(?:\*|×|\\times|\\cdot|x|X)\s*\{?10\}?\s*\{?\^\s*\{?\s*([-+]?\s*\d+)\s*\}?',
            r'\{?\s*([-+]?\s*[\d\.]+)\s*\}?\s*(?:\*|×|\\times|\\cdot|x|X)\s*10\s*\*\*\s*\{?\s*([-+]?\s*\d+)\s*\}?'
        ]
        for pattern in sci_pattern_list:
            for match in re.finditer(pattern, self.original_text):
                start, end = match.span()
                if self._overlaps_forbidden(start, end):
                    continue
                self._add_forbidden_zone(start, end)

                coeff = match.group(1)
                coeff_start = match.start(1)
                coeff_end = match.end(1)
                self.matches.append((coeff_start, coeff_end, coeff))

                if match.group(2) and self.exp_need:
                    exp = match.group(2)
                    exp_start = match.start(2)
                    exp_end = match.end(2)
                    self.matches.append((exp_start, exp_end, exp))

    def _generate_template(self):
        self.matches.sort(key=lambda x: x[0])
        parts = []
        last_end = 0

        for idx, (start, end, value) in enumerate(self.matches):
            param_id = f"param{idx}"
            self.param_ids.append(param_id)
            self.param_values[param_id] = value

            parts.append(self.original_text[last_end:start])
            parts.append(f"<<{param_id}>>")
            last_end = end

        parts.append(self.original_text[last_end:])
        self.template = "".join(parts)

    def get_current_text(self):
        text = self.template
        for param_id, value in self.param_values.items():
            value_str = str(value)
            text = text.replace(f"<<{param_id}>>", value_str)
        return text

    def set_param(self, param_id, value):
        if param_id in self.param_values:
            self.param_values[param_id] = value
        else:
            raise KeyError(f"未知参数: {param_id}")

    def get_params(self):
        return self.param_values.copy()

    def list_params(self):
        return [(param_id, self.param_values[param_id]) for param_id in self.param_ids]


