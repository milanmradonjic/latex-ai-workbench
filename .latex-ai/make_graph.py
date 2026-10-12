"""Read-only Make lexical facts shared by adapters, ownership and validation.

This never expands Make code or invokes Make. Consumers decide whether unresolved
syntax requires a conservative full check or an explicit ownership adapter.
"""
from dataclasses import dataclass, field
from pathlib import Path
import re

from core import WorkbenchError

MANAGED = re.compile(r'# BEGIN LATEX AI WORKBENCH.*?# END LATEX AI WORKBENCH', re.S)
LITERAL = re.compile(r'[A-Za-z0-9_./-]+\Z')
ASSIGNMENT = re.compile(r'(?:(?:override|private|export|unexport)\s+)*([\w.-]+)\s*(?:::|:|\+|\?|!)?=')
INCLUDE = re.compile(r'^\s*(-include|sinclude|include)\s+(.+)$')


MAKEFILES = ("GNUmakefile", "makefile", "Makefile")  # the order in which GNU Make itself looks for one


def active_makefile(project):
    """Name of the file GNU Make reads in this directory, or None.

    Actual directory entries are compared first: on a case-insensitive filesystem ``makefile`` and
    ``Makefile`` are one file, and the spelling on disk is the one the installer registered.
    """
    try:
        present = {path.name for path in project.iterdir()}
    except OSError:
        return None
    return next((name for name in MAKEFILES if name in present), None) or next((name for name in MAKEFILES if (project / name).is_file()), None)


def makefile_text(project):
    name = active_makefile(project)
    try:
        return (project / name).read_text(encoding="utf-8") if name else ""
    except (OSError, ValueError):
        return ""



def partition(value, separators):
    """Split outside escapes and Make references; preserve expressions verbatim."""
    depth, escaped = 0, False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == '\\':
            escaped = True
        elif char in '({':
            depth += 1
        elif char in ')}':
            depth = max(0, depth - 1)
        elif char in separators and not depth:
            return value[:index], char, value[index + 1:]
    return value, '', ''


@dataclass
class Rule:
    targets: tuple
    prerequisites: str
    separator: str = ':'
    recipes: list = field(default_factory=list)
    variables: tuple = ()

    @property
    def literal(self):
        return all(LITERAL.fullmatch(name) for name in self.targets)

    @property
    def unresolved(self):
        return not self.literal or any(char in self.prerequisites for char in '$%*?[')


@dataclass
class Graph:
    rules: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    unresolved: bool = False
    files: set = field(default_factory=set)
    recipe_prefix: bool = False

    @property
    def targets(self):
        return {name for rule in self.rules if rule.literal for name in rule.targets}

    @property
    def edges(self):
        return [(name, rule.prerequisites) for rule in self.rules if rule.literal
                for name in rule.targets]

    def separator(self, name):
        separators = {rule.separator for rule in self.rules if name in rule.targets}
        if len(separators) > 1:
            raise WorkbenchError(f'Ambiguous single- and double-colon rules for {name}',
                                 hint='use one rule style across conditional branches, or an explicit project adapter')
        return next(iter(separators), ':')


def read(text, project=None, managed=True):
    graph, seen = Graph(), set()
    def source(value):
        value = MANAGED.sub('', value) if managed else value
        graph.sources.append(value)
        current = None
        for line in value.replace('\\\n', ' ').splitlines():
            if line.startswith('\t'):
                if current is not None:
                    current.recipes.append(line[1:])
                continue
            clean = partition(line, '#')[0].strip()
            if not clean:
                continue  # GNU Make keeps the recipe association across comments/blank lines.
            if '$(eval' in clean or '${eval' in clean:
                graph.unresolved = True  # assignments can also synthesize check rules
            if clean.split(None, 1)[0] in {'ifeq', 'ifneq', 'ifdef', 'ifndef', 'else', 'endif'}:
                continue  # conditionals do not break GNU Make's recipe association
            included = INCLUDE.match(clean)
            if included:
                current = None
                for name in included[2].split():
                    if any(char in name for char in '$*?[%\\'):
                        graph.unresolved = True
                        continue
                    if project is None:
                        continue
                    path = (Path(project) / name).resolve()
                    if not path.is_relative_to(Path(project).resolve()):
                        graph.unresolved = True
                        continue
                    graph.files.add(path.relative_to(Path(project).resolve()).as_posix())
                    if path in seen:
                        continue
                    seen.add(path)
                    try:
                        source(path.read_text(encoding='utf-8'))
                    except (OSError, ValueError):
                        # Even an optional include can be rebuilt by Make before
                        # evaluating check; absence does not prove no check exists.
                        graph.unresolved = True
                continue
            assignment = ASSIGNMENT.match(clean)
            if assignment:
                if assignment[1] == '.RECIPEPREFIX' and clean[assignment.end():].strip():
                    graph.recipe_prefix = graph.unresolved = True
                current = None
                continue
            targets, separator, remaining = partition(clean, ':')
            if not separator:
                current = None
                # Conditional directives may contain rules in either branch. We inspect both.
                if clean.startswith(('define ', 'eval ', '$(eval', '${eval', '.RECIPEPREFIX')):
                    graph.unresolved = True
                continue
            if remaining.startswith(':'):
                separator, remaining = '::', remaining[1:]
            if remaining.startswith('='):
                current = None
                continue
            names = tuple(targets.split())
            if not names:
                current = None
                continue
            variable = ASSIGNMENT.match(remaining.lstrip())
            prerequisites, _, inline = partition(remaining, ';')
            current = Rule(names, '' if variable else prerequisites.strip(), separator,
                           [inline] if inline.strip() else [], (variable[1],) if variable else ())
            graph.rules.append(current)
            if not current.literal:
                graph.unresolved = True
    source(text)
    return graph
