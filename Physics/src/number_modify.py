import re

def get_unit_template():
    # Base unit structure (allows internal modifiers)
    base_unit = r"\{?\\mathrm\s*\{[^}]*?\}\}?\}?"

    # Superscript/subscript processor (supports ^{...} and _^{...} forms)
    super_sub = r"(?:\s*\\?[\^\^]\s*(?:\{[^}]*?\}|[^{}\s]+))?"

    # Pattern 1: Base units (with external superscript/subscript)
    pattern1 = rf"({base_unit}{super_sub})"

    # Pattern 2: Compound units (with connectors and modifiers)
    connector = r"(?:\\cdot|/|\\times)"
    pattern2 = rf"((?:{base_unit}{super_sub}\s*{connector}?\s*)+)"

    # Pattern 3: Parenthesized units (with enclosed modifiers)
    bracketed = r"\\left(\\\{)?[^()]*?\\right(\\\})?"
    pattern3 = rf"({bracketed}\s*{super_sub})"

    # Pattern 4: Superscript-prefixed units (remain unchanged)
    pattern4 = rf"(\^{{[^}}\d]*?}}\s*{base_unit})"
    
    # Pattern 5: Pure superscript units, remove specific symbols
    pattern5 = r"(\^\{?\s*\\[a-zA-Z]+\b\}?)"

    # Match all cases
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
        
        # Intervals for forbidden matching
        self.forbidden_zones = []
        
        # Processing flow
        self._extract_numbers()
        self._generate_template()

    def _overlaps_forbidden(self, start, end):
        """Check if the interval overlaps with any forbidden regions"""
        for zone in self.forbidden_zones:
            z_start, z_end = zone
            if start < z_end and end > z_start:
                return True
        return False

    def _add_forbidden_zone(self, start, end):
        """Add forbidden regions and merge adjacent intervals"""
        self.forbidden_zones.append((start, end))
        # Merge overlapping intervals
        self.forbidden_zones.sort(key=lambda x: x[0])
        merged = []
        for start, end in self.forbidden_zones:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        self.forbidden_zones = merged

    def _extract_numbers(self):
        """Main extraction function: processes various number types in sequence"""
        # Step 1: Mark subscript regions (forbidden for matching), unit regions
        subscript_pattern = r'_\s*{[^}]*}'
        for match in re.finditer(subscript_pattern, self.original_text):
            self._add_forbidden_zone(match.start(), match.end())
        unit_pattern = get_unit_template()
        for match in re.finditer(unit_pattern, self.original_text):
            self._add_forbidden_zone(match.start(), match.end())

        
        # Step 2: Extract scientific notation
        self._extract_scientific_notation()

        # Step 3: Mark all superscript regions (except exponents already extracted by scientific notation)
        superscript_pattern = r'\^\s*\{?[^}]*\}?'
        for match in re.finditer(superscript_pattern, self.original_text):
            # Check if already covered by scientific notation
            # if not self._overlaps_forbidden(match.start(), match.end()):
            self._add_forbidden_zone(match.start(), match.end())
        
        # Step 4: Extract numbers within curly braces
        braced_pattern = r'([-+]?\s*\{?\d+(?:\.\d+)?\s*\}?)'
        for match in re.finditer(braced_pattern, self.original_text):
            start, end = match.span()
            if not self._overlaps_forbidden(start, end):
                value = match.group(1)
                value = re.sub(r'\{|\}', '', value)
                self.matches.append((start, end, value))
                self._add_forbidden_zone(start, end)
        
        # Step 5: Extract standalone numbers
        # Enhanced standalone number pattern
        standalone_pattern = r'(?<!\w)([-+]?\s*\d+(?:\.\d+)?)(?=[^\w]|$)'
        for match in re.finditer(standalone_pattern, self.original_text):
            start, end = match.span()
            value_str = match.group(0)
            if not self._overlaps_forbidden(start, end):
                value = value_str
                self.matches.append((start, end, value))
                self._add_forbidden_zone(start, end)
        

    def _extract_scientific_notation(self):
        """Extract the coefficient and exponent in scientific notation while marking the related regions as forbidden zones"""
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
                # Mark the entire expression as a forbidden zone
                self._add_forbidden_zone(start, end)
                
                # Extract coefficient
                coeff = match.group(1)
                coeff_start = match.start(1)
                coeff_end = match.end(1)
                self.matches.append((coeff_start, coeff_end, coeff))
                
                # Extract exponent (if present)
                if match.group(2) and self.exp_need:
                    exp = match.group(2)
                    exp_start = match.start(2)
                    exp_end = match.end(2)
                    self.matches.append((exp_start, exp_end, exp))

    def _generate_template(self):
        """Generate template and parameter IDs, ensuring correct ordering"""
        # Sort by starting position
        self.matches.sort(key=lambda x: x[0])
        
        parts = []
        last_end = 0
        
        for idx, (start, end, value) in enumerate(self.matches):
            param_id = f"param{idx}"
            self.param_ids.append(param_id)
            self.param_values[param_id] = value
            # Add text preceding the match
            parts.append(self.original_text[last_end:start])
            # Add placeholder
            parts.append(f"<<{param_id}>>")
            last_end = end
        
        # Add remaining text
        parts.append(self.original_text[last_end:])
        self.template = "".join(parts)

    def get_params(self):
        """Get all parameters."""
        return self.param_values.copy()

    def list_params(self):
        """List the parameters in order."""
        return [(param_id, self.param_values[param_id]) for param_id in self.param_ids]
