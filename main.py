# -*- coding: utf-8 -*-

from manim import *
import json
import os
import math
import ast
import operator
import argparse
import platform
import sys
from typing import List, Dict, Tuple, Optional, Callable, Any

# ==========================
# settings
# ==========================
config.format = "mp4"
config.frame_rate = 30
config.pixel_height = 1080
config.pixel_width = 1920

PERFORMANCE_MODE = 'balanced'
HW_ACCEL_DISABLED = False

def get_performance_settings():
    modes = {
        'quality': {
            'root_tolerance': 1e-14,
            'root_samples': 6000,
            'graph_samples': 500,
            'label_font_scale': 1.0,
            'show_labels': True,
            'smoothing': True,
            'description': 'High-precision mode - Best quality and accuracy',
        },
        'balanced': {
            'root_tolerance': 1e-12,
            'root_samples': 4000,
            'graph_samples': 300,
            'label_font_scale': 1.0,
            'show_labels': True,
            'smoothing': True,
            'description': 'Balanced mode - High precision with speed',
        },
        'speed': {
            'root_tolerance': 1e-8,
            'root_samples': 2000,
            'graph_samples': 150,
            'label_font_scale': 0.95,
            'show_labels': True,
            'smoothing': True,
            'description': 'Speed priority - Preview only',
        },
        'ultra_fast': {
            'root_tolerance': 1e-6,
            'root_samples': 1000,
            'graph_samples': 80,
            'label_font_scale': 0.9,
            'show_labels': False,
            'smoothing': False,
            'description': 'Ultra-fast mode - Quick preview',
        },
    }
    return modes.get(PERFORMANCE_MODE, modes['balanced'])

def setup_hardware_acceleration():
    if HW_ACCEL_DISABLED:
        return False, "Hardware acceleration disabled (user specified)"
    if platform.system() != 'Windows':
        return False, "Non-Windows platform, hardware acceleration skipped"
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi'], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            config.renderer = "cairo"
            config.save_last_frame = False
            return True, "Detected NVIDIA GPU, NVENC hardware encoding enabled"
        else:
            return False, "No NVIDIA GPU detected, using software encoding"
    except:
        return False, "Hardware acceleration detection failed, using software encoding"

_PERF_CACHE = {}
def perf(key: str) -> Any:
    global _PERF_CACHE
    if not _PERF_CACHE:
        _PERF_CACHE = get_performance_settings()
    return _PERF_CACHE.get(key)

# ==========================
# Safe mathematical expression evaluation
# ==========================
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

SAFE_FUNCTIONS = {
    "abs": abs,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "exp": math.exp,
    "log": math.log,
    "sqrt": math.sqrt,
    "pow": pow,
    "floor": math.floor,
    "ceil": math.ceil,
    "round": round,
    "max": max,
    "min": min,
}

def safe_eval_expr(expr: str, variables: Dict[str, float]) -> float:
    try:
        tree = ast.parse(expr, mode='eval')
        return _eval_ast(tree.body, variables)
    except Exception as e:
        raise ValueError(f"Expression evaluation failed: {expr}, Error: {e}")

def _eval_ast(node: ast.AST, variables: Dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
    elif isinstance(node, ast.Name):
        if node.id in variables:
            return variables[node.id]
        if node.id == 'math':
            return math
        if node.id in SAFE_FUNCTIONS:
            raise ValueError(f"Function missing arguments: {node.id}")
        raise ValueError(f"Unknown variable: {node.id}")
    elif isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id == 'math':
            func_name = node.attr
            if hasattr(math, func_name) and callable(getattr(math, func_name)):
                return getattr(math, func_name)
        obj = _eval_ast(node.value, variables)
        if hasattr(obj, node.attr):
            return getattr(obj, node.attr)
        raise ValueError(f"Unsupported attribute access: {node.attr}")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _eval_ast(node.left, variables)
        right = _eval_ast(node.right, variables)
        return SAFE_OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _eval_ast(node.operand, variables)
        return SAFE_OPERATORS[op_type](operand)
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in SAFE_FUNCTIONS:
                func = SAFE_FUNCTIONS[func_name]
            else:
                raise ValueError(f"Unsupported function: {func_name}")
        elif isinstance(node.func, ast.Attribute):
            func = _eval_ast(node.func, variables)
            if not callable(func):
                raise ValueError(f"Not callable function")
        else:
            raise ValueError(f"Unsupported function call syntax: {type(node.func).__name__}")
        if node.keywords:
            raise ValueError("Unsupported keyword arguments")
        args = [_eval_ast(arg, variables) for arg in node.args]
        return func(*args)
    else:
        raise ValueError(f"Unsupported expression type: {type(node).__name__}")

def create_safe_function(expr: str, var_names: List[str]) -> Callable:
    tree = ast.parse(expr, mode='eval')
    def func(*args):
        if len(args) != len(var_names):
            raise ValueError(f"Parameter count mismatch: expected {len(var_names)} args, got {len(args)}")
        variables = dict(zip(var_names, args))
        return _eval_ast(tree.body, variables)
    return func

# ==========================
# High-precision root finding
# ==========================
def find_roots(
    func: Callable[[float], float],
    x_min: float,
    x_max: float,
    num_steps: Optional[int] = None,
    tolerance: Optional[float] = None,
) -> List[float]:
    if num_steps is None:
        num_steps = perf('root_samples') or 4000
    if tolerance is None:
        tolerance = perf('root_tolerance') or 1e-12

    roots = []
    step = (x_max - x_min) / num_steps

    candidates = []
    x_prev = x_min
    try:
        f_prev = func(x_prev)
    except:
        f_prev = float('nan')
    f_prev2 = float('nan')

    for i in range(1, num_steps + 1):
        x_curr = x_min + i * step
        try:
            f_curr = func(x_curr)
        except:
            f_curr = float('nan')
            x_prev, f_prev = x_curr, f_curr
            continue

        if math.isnan(f_prev) or math.isinf(f_prev) or \
           math.isnan(f_curr) or math.isinf(f_curr):
            f_prev2 = f_prev
            x_prev, f_prev = x_curr, f_curr
            continue

        if abs(f_curr) < step * 1.5:
            candidates.append((x_curr - step * 4, x_curr + step * 4))
            f_prev2 = f_prev
            x_prev, f_prev = x_curr, f_curr
            continue

        if f_prev * f_curr < 0:
            candidates.append((x_prev, x_curr))

        if i >= 2:
            try:
                if not (math.isnan(f_prev2) or math.isinf(f_prev2)):
                    if f_prev2 > f_prev and f_prev < f_curr:
                        if abs(f_prev) < step * 25:
                            candidates.append((x_prev - step * 1.5, x_curr))
                        elif f_prev > 0 and f_prev < abs(f_prev2) * 0.25:
                            candidates.append((x_prev - step * 1.5, x_curr))
            except:
                pass

        f_prev2 = f_prev
        x_prev, f_prev = x_curr, f_curr

    max_iterations = int(120 + math.log10(1/tolerance) * 25)

    for a, b in candidates:
        try:
            fa, fb = func(a), func(b)
            if fa * fb <= 0:
                if fa > 0:
                    a, b = b, a
                    fa, fb = fb, fa
                for _ in range(max_iterations):
                    mid = (a + b) / 2
                    fm = func(mid)
                    if abs(fm) < tolerance or abs(b - a) < tolerance * 0.05:
                        break
                    if fm <= 0:
                        a, fa = mid, fm
                    else:
                        b, fb = mid, fm
                root_x = (a + b) / 2
                if abs(func(root_x)) < tolerance * 1000:
                    roots.append(root_x)
            else:
                gr = (math.sqrt(5) - 1) / 2
                c = b - gr * (b - a)
                d = a + gr * (b - a)
                fc = func(c)
                fd = func(d)
                for _ in range(max_iterations):
                    if fc < fd:
                        b = d
                        d = c
                        fb = fd
                        fd = fc
                        c = b - gr * (b - a)
                        fc = func(c)
                    else:
                        a = c
                        c = d
                        fa = fc
                        fc = fd
                        d = a + gr * (b - a)
                        fd = func(d)
                    if abs(b - a) < tolerance * 0.05:
                        break
                min_x = (a + b) / 2
                min_val = func(min_x)
                if min_val >= 0 and min_val < abs(x_max - x_min) * 1e-10:
                    left = max(a, min_x - step * 3)
                    right = min(b, min_x + step * 3)
                    best_x = min_x
                    best_slope_change = 0
                    search_steps = 200
                    search_step = (right - left) / search_steps
                    prev_slope = None
                    for si in range(1, search_steps + 1):
                        x_left = left + (si - 1) * search_step
                        x_right = left + si * search_step
                        try:
                            y_left = func(x_left)
                            y_right = func(x_right)
                            slope = (y_right - y_left) / search_step if search_step != 0 else 0
                            if prev_slope is not None:
                                slope_change = abs(slope - prev_slope)
                                if slope_change > best_slope_change:
                                    best_slope_change = slope_change
                                    best_x = (x_left + x_right) / 2
                        except:
                            pass
                    if best_slope_change > 1e-8:
                        if abs(func(best_x)) < abs(x_max - x_min) * 1e-8:
                            roots.append(best_x)
                        else:
                            roots.append(min_x)
                    else:
                        roots.append(min_x)
        except:
            continue
    unique_roots = []
    merge_threshold = max(tolerance * 10, abs(x_max - x_min) * 1e-8)
    for root in sorted(roots):
        if not any(abs(root - ur) < merge_threshold for ur in unique_roots):
            unique_roots.append(root)
    return unique_roots

# ==========================
# Smart range calculation
# ==========================
def calculate_smart_ranges(
    func: Callable[[float], float],
    initial_x_range: Tuple[float, float],
    target_y_range: Tuple[float, float] = (-5, 5),
    max_x_extend: float = 20,
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    x_min, x_max = initial_x_range
    def sample_y_values(xs, xe):
        y_vals = []
        step = (xe - xs) / 1500
        for i in range(1501):
            x = xs + i * step
            try:
                y = func(x)
                if not (math.isnan(y) or math.isinf(y)):
                    y_vals.append(y)
            except:
                continue
        return y_vals
    y_values = sample_y_values(x_min, x_max)
    if not y_values:
        return initial_x_range, (-2, 2)
    current_min_y, current_max_y = min(y_values), max(y_values)
    target_min_y, target_max_y = target_y_range
    if current_min_y >= target_min_y and current_max_y <= target_max_y:
        padding = (current_max_y - current_min_y) * 0.2
        return initial_x_range, (current_min_y - padding, current_max_y + padding)
    try:
        y0 = func(0)
        slope = (func(0.0001) - y0) / 0.0001
    except:
        slope = 0
    if abs(slope) > 10:
        if slope > 0:
            needed_x_min = (target_min_y - y0) / slope
            x_min = min(x_min, needed_x_min - 1)
        else:
            needed_x_max = (target_min_y - y0) / slope
            x_max = max(x_max, needed_x_max + 1)
    x_min = max(x_min, -max_x_extend)
    x_max = min(x_max, max_x_extend)
    y_values = sample_y_values(x_min, x_max)
    if not y_values:
        return (x_min, x_max), (-2, 2)
    min_y, max_y = min(y_values), max(y_values)
    y_range = max_y - min_y
    padding = y_range * 0.15
    if min_y < 0 < max_y:
        if abs(min_y) < y_range * 0.1:
            min_y = -y_range * 0.2
        if abs(max_y) < y_range * 0.1:
            max_y = y_range * 0.2
    return (x_min, x_max), (min_y - padding, max_y + padding)

# ==========================
# Coordinate dashed line tool
# ==========================
def create_coord_dashes(
    axes: Axes,
    x: float,
    y: float,
    scale: float,
) -> VGroup:
    dash_style = {"color": GRAY, "stroke_width": 1.5 * scale}
    elements = VGroup()
    label_font_size = 22 * scale
    eps = 1e-9
    if abs(y) > eps:
        dash_x = DashedLine(axes.c2p(x, y), axes.c2p(x, 0), **dash_style)
        elements.add(dash_x)
    if abs(x) > eps:
        x_axis_point = axes.c2p(x, 0)
        x_label_dir = DOWN if y >= 0 else UP
        x_buff = 0.18 * scale
        x_label = MathTex(f"{x:.2f}", font_size=label_font_size, color=YELLOW)
        x_label.set_stroke(color=BLACK, width=3.5, background=True)
        x_label.next_to(x_axis_point, x_label_dir, buff=x_buff)
        elements.add(x_label)
    if abs(x) > eps:
        dash_y = DashedLine(axes.c2p(x, y), axes.c2p(0, y), **dash_style)
        elements.add(dash_y)
    if abs(y) > eps:
        y_axis_point = axes.c2p(0, y)
        y_label_dir = LEFT if x >= 0 else RIGHT
        y_buff = 0.18 * scale
        y_label = MathTex(f"{y:.2f}", font_size=label_font_size, color=YELLOW)
        y_label.set_stroke(color=BLACK, width=3.5, background=True)
        y_label.next_to(y_axis_point, y_label_dir, buff=y_buff)
        elements.add(y_label)
    return elements

def safe_math_tex(tex_string: str, **kwargs) -> Mobject:
    try:
        return MathTex(tex_string, **kwargs)
    except Exception as e:
        print(f"❌ LaTeX formula error: {tex_string} - {e}")
        return Text("Formula error", color=RED, **kwargs)

# ==========================
# JSON reading
# ==========================
def load_math_data(json_file_path: str) -> Optional[Dict]:
    if not os.path.exists(json_file_path):
        print(f"Error: File {json_file_path} not found")
        return None
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print("✅ JSON read successfully")
        return data
    except Exception as e:
        print(f"❌ Read failed: {str(e)}")
        return None

# ==========================
# Dynamic function class
# ==========================
class DynamicFunction:
    def __init__(
        self,
        axes: Axes,
        function_str: str,
        variables: Dict[str, Dict],
        x_range: Tuple[float, float],
        color: str = BLUE,
        scale: float = 1.0,
        show_axis_intersections: bool = True,
        function_points: Optional[List[Dict]] = None,
        moving_axis_point: Optional[List[Dict]] = None,
        moving_function_point: Optional[List[Dict]] = None,
    ):
        self.axes = axes
        self.function_str = function_str
        self.variables_info = variables
        self.x_range = x_range
        self.color = color
        self.scale = scale
        self.show_axis_intersections = show_axis_intersections
        self.function_points = function_points or []
        self.moving_axis_point = moving_axis_point or []
        self.moving_function_point = moving_function_point or []

        self.trackers = {
            k: ValueTracker(v["start"]) for k, v in variables.items()
        }

        # Moving axis points
        self.moving_axis_trackers = []
        self.moving_axis_animations = []
        for mp in self.moving_axis_point:
            axis = mp.get("axis", "x")
            start = float(mp.get("start", 0))
            end = float(mp.get("end", 0))
            rt = float(mp.get("run_time", 3))
            label = mp.get("label", "")
            tracker = ValueTracker(start)
            self.moving_axis_trackers.append({
                "tracker": tracker,
                "axis": axis,
                "end": end,
                "run_time": rt,
                "label": label
            })
            self.moving_axis_animations.append(tracker.animate.set_value(end))

        # Function curve moving points
        self.moving_func_trackers = []
        self.moving_func_animations = []
        for mfp in self.moving_function_point:
            x_start = float(mfp.get("x_start", 0))
            x_end = float(mfp.get("x_end", 1))
            rt = float(mfp.get("run_time", 3))
            label = mfp.get("label", "")
            tracker = ValueTracker(x_start)
            self.moving_func_trackers.append({
                "tracker": tracker,
                "x_end": x_end,
                "run_time": rt,
                "label": label
            })
            self.moving_func_animations.append(tracker.animate.set_value(x_end))

        var_names = ["x"] + list(self.trackers.keys())
        self._func = create_safe_function(function_str, var_names)

        self._graph_samples = perf('graph_samples') or 300
        self._use_smoothing = perf('smoothing') if perf('smoothing') is not None else True
        self._show_labels = perf('show_labels') if perf('show_labels') is not None else True
        self._eval_cache = {}
        self._last_vars = None

        self.graph = always_redraw(self._plot)
        self.moving_axis_group = always_redraw(self.create_moving_axis_points)
        self.moving_func_group = always_redraw(self.create_moving_function_points)

    def _get_vars_tuple(self) -> Tuple:
        return tuple(t.get_value() for t in self.trackers.values())

    def evaluate(self, x: float) -> float:
        vars_tuple = self._get_vars_tuple()
        if vars_tuple != self._last_vars:
            self._last_vars = vars_tuple
            self._eval_cache.clear()
        cache_key = (x, vars_tuple)
        if cache_key in self._eval_cache:
            return self._eval_cache[cache_key]
        result = self._func(x, *[vars_tuple[i] for i in range(len(self.trackers))])
        self._eval_cache[cache_key] = result
        return result

    def _plot(self) -> VMobject:
        plot_x_min = max(self.x_range[0], self.axes.x_range[0])
        plot_x_max = min(self.x_range[1], self.axes.x_range[1])
        if plot_x_min >= plot_x_max:
            return VMobject()
        x_range_size = plot_x_max - plot_x_min
        base_samples = max(self._graph_samples, int(x_range_size * 40))
        base_step = x_range_size / base_samples
        try:
            try:
                zeros = find_roots(self.evaluate, plot_x_min, plot_x_max, min(base_samples, 6000), 1e-14)
            except:
                zeros = []
            points = []
            for i in range(base_samples + 1):
                x = plot_x_min + i * base_step
                try:
                    y = self.evaluate(x)
                    y = max(y, 0.0) if 'abs' in self.function_str else y
                    if math.isnan(y) or math.isinf(y):
                        points.append((x, None))
                    else:
                        points.append((x, y))
                except:
                    points.append((x, None))
            zero_set = set()
            for zero_x in zeros:
                if plot_x_min <= zero_x <= plot_x_max:
                    zero_set.add(round(zero_x, 14))
                    points.append((zero_x, 0.0))
                    for k in range(1, 21):
                        eps = base_step * 0.005 * k
                        lx = zero_x - eps
                        rx = zero_x + eps
                        if lx >= plot_x_min:
                            ly = max(self.evaluate(lx), 0.0) if 'abs' in self.function_str else self.evaluate(lx)
                            if not math.isnan(ly):
                                points.append((lx, ly))
                        if rx <= plot_x_max:
                            ry = max(self.evaluate(rx), 0.0) if 'abs' in self.function_str else self.evaluate(rx)
                            if not math.isnan(ry):
                                points.append((rx, ry))
            points.sort(key=lambda p: p[0])
            refined_points = []
            for i in range(len(points)-1):
                x0, y0 = points[i]
                x1, y1 = points[i+1]
                refined_points.append((x0, y0))
                if y0 is not None and y1 is not None:
                    dx = x1 - x0
                    if dx > base_step * 1.2:
                        ne = min(8, int(dx / base_step * 0.9))
                        for j in range(1, ne+1):
                            mx = x0 + dx * j / (ne+1)
                            my = max(self.evaluate(mx),0) if 'abs' in self.function_str else self.evaluate(mx)
                            if not math.isnan(my):
                                refined_points.append((mx, my))
            if points:
                refined_points.append(points[-1])
            seen_x = {}
            unique_points = []
            for x,y in refined_points:
                if y is None:
                    continue
                xk = round(x,14)
                if xk in zero_set:
                    continue
                if xk not in seen_x:
                    seen_x[xk] = y
                    unique_points.append((x,y))
            for zx in zeros:
                zk = round(zx,14)
                seen_x[zk] = 0.0
                unique_points.append((zx, 0.0))
            unique_points.sort(key=lambda p:p[0])
            has_cusp = len(zeros) > 0
            if not has_cusp and len(unique_points)>=3:
                for i in range(1, len(unique_points)-1):
                    x0,y0 = unique_points[i-1]
                    x1,y1 = unique_points[i]
                    x2,y2 = unique_points[i+1]
                    dx1=x1-x0
                    dx2=x2-x1
                    if dx1>0 and dx2>0:
                        s1=(y1-y0)/dx1
                        s2=(y2-y1)/dx2
                        sc=abs(s2-s1)
                        am=(abs(s1)+abs(s2))/2+0.001
                        if sc>am*0.4 and sc>0.05:
                            has_cusp=True
                            break
            if len(unique_points)<2:
                return VMobject()
            graph = VMobject(stroke_width=2*self.scale, color=self.color)
            y_range_size = self.axes.y_range[1]-self.axes.y_range[0]
            seg_x_list = []
            last_x = plot_x_min
            for z in sorted(zeros):
                if plot_x_min < z < plot_x_max:
                    seg_x_list.append((last_x, z))
                    last_x = z
            seg_x_list.append((last_x, plot_x_max))
            for smin, smax in seg_x_list:
                seg_pts = [self.axes.c2p(x,y) for x,y in unique_points if smin-1e-12 <=x <= smax+1e-12]
                if len(seg_pts)<2:
                    continue
                valid = [seg_pts[0]]
                for i in range(1, len(seg_pts)):
                    if abs(seg_pts[i][1]-seg_pts[i-1][1]) <= y_range_size*0.5:
                        valid.append(seg_pts[i])
                    else:
                        if len(valid)>=2:
                            sub = VMobject()
                            if self._use_smoothing and not has_cusp:
                                sub.set_points_smoothly(valid)
                            else:
                                sub.set_points_as_corners(valid)
                            sub.set_stroke(color=self.color, width=2*self.scale)
                            graph.add(sub)
                        valid = [seg_pts[i]]
                if len(valid)>=2:
                    sub = VMobject()
                    if self._use_smoothing and not has_cusp:
                        sub.set_points_smoothly(valid)
                    else:
                        sub.set_points_as_corners(valid)
                    sub.set_stroke(color=self.color, width=2*self.scale)
                    graph.add(sub)
            return graph
        except Exception as e:
            print(f"⚠️  Function plot warning: {e}")
            try:
                step = x_range_size / base_samples
                return self.axes.plot(self.evaluate, x_range=[plot_x_min, plot_x_max, step], use_smoothing=False, stroke_width=2*self.scale, color=self.color)
            except:
                return VMobject()

    def create_moving_axis_points(self) -> VGroup:
        group = VGroup()
        eps = 1e-9
        for item in self.moving_axis_trackers:
            t = item["tracker"]
            axis = item["axis"]
            label_text = item["label"]
            if axis == "x":
                x_val = t.get_value()
                y_val = 0.0
            else:
                x_val = 0.0
                y_val = t.get_value()
            
            dot = Dot(
                self.axes.c2p(x_val, y_val),
                radius=0.07 * self.scale,
                color=YELLOW
            )
            dot.set_stroke(color=BLACK, width=2.5, background=True)
            dash_group = create_coord_dashes(self.axes, x_val, y_val, self.scale)
            sub_vg = VGroup(dot, dash_group)
            
            if label_text.strip() != "":
                lab = MathTex(label_text, font_size=24*self.scale, color=YELLOW)
                lab.set_stroke(BLACK, width=3.5, background=True)
                dx = 0.15 if x_val >= 0 else -0.15
                dy = 0.15 if y_val >=0 else -0.15
                lab.next_to(dot, np.array([dx, dy, 0]), buff=0.12)
                sub_vg.add(lab)
            group.add(sub_vg)
        return group

    def create_moving_function_points(self) -> VGroup:
        group = VGroup()
        for item in self.moving_func_trackers:
            t = item["tracker"]
            label_text = item["label"]
            x_val = t.get_value()
            try:
                y_val = self.evaluate(x_val)
            except:
                continue
            
            if not (self.axes.x_range[0] <= x_val <= self.axes.x_range[1] and
                    self.axes.y_range[0] <= y_val <= self.axes.y_range[1]):
                continue
            
            dot = Dot(
                self.axes.c2p(x_val, y_val),
                radius=0.07 * self.scale,
                color=YELLOW
            )
            dot.set_stroke(color=BLACK, width=2.5, background=True)
            dash_group = create_coord_dashes(self.axes, x_val, y_val, self.scale)
            sub_vg = VGroup(dot, dash_group)
            
            if label_text.strip() != "":
                lab = MathTex(label_text, font_size=24*self.scale, color=YELLOW)
                lab.set_stroke(BLACK, width=3.5, background=True)
                label_dir = UP + RIGHT if x_val >= 0 else UP + LEFT
                lab.next_to(dot, label_dir, buff=0.15 * self.scale)
                sub_vg.add(lab)
            group.add(sub_vg)
        return group

    def create_axis_intersections(self) -> VGroup:
        intersections = VGroup()
        if not self._show_labels:
            try:
                x_roots = find_roots(self.evaluate, self.axes.x_range[0], self.axes.x_range[1])
                for x in x_roots:
                    y=0.0
                    if self.axes.y_range[0]<=y<=self.axes.y_range[1]:
                        p = Dot(self.axes.c2p(x,y), radius=0.07*self.scale, color=YELLOW)
                        p.set_stroke(BLACK,2.5,True)
                        intersections.add(p)
                if self.axes.x_range[0]<=0<=self.axes.x_range[1]:
                    y=self.evaluate(0)
                    if self.axes.y_range[0]<=y<=self.axes.y_range[1]:
                        p = Dot(self.axes.c2p(0,y), radius=0.07*self.scale, color=YELLOW)
                        p.set_stroke(BLACK,2.5,True)
                        intersections.add(p)
            except Exception as e:
                print(f"⚠️  Intersection calculation warning: {e}")
            return intersections
        try:
            x_roots = find_roots(self.evaluate, self.axes.x_range[0], self.axes.x_range[1])
            for x in x_roots:
                y=0.0
                if self.axes.y_range[0]<=y<=self.axes.y_range[1]:
                    p = Dot(self.axes.c2p(x,y), radius=0.07*self.scale, color=YELLOW)
                    p.set_stroke(BLACK,2.5,True)
                    dashes = create_coord_dashes(self.axes, x, y, self.scale)
                    intersections.add(p, dashes)
            if self.axes.x_range[0]<=0<=self.axes.x_range[1]:
                y=self.evaluate(0)
                if self.axes.y_range[0]<=y<=self.axes.y_range[1]:
                    p = Dot(self.axes.c2p(0,y), radius=0.07*self.scale, color=YELLOW)
                    p.set_stroke(BLACK,2.5,True)
                    dashes = create_coord_dashes(self.axes, 0, y, self.scale)
                    intersections.add(p, dashes)
        except Exception as e:
            print(f"⚠️  Intersection calculation warning: {e}")
        return intersections

    def create_custom_points(self) -> VGroup:
        points_group = VGroup()
        try:
            for p_info in self.function_points:
                x = p_info.get('x', 0)
                label = p_info.get('label', '')
                y = self.evaluate(x)
                if (self.axes.x_range[0] <= x <= self.axes.x_range[1] and
                    self.axes.y_range[0] <= y <= self.axes.y_range[1]):
                    point = Dot(self.axes.c2p(x, y), radius=0.07*self.scale, color=YELLOW)
                    point.set_stroke(color=BLACK, width=2.5, background=True)
                    dashes = create_coord_dashes(self.axes, x, y, self.scale)
                    if label:
                        tex_label = MathTex(label, font_size=24*self.scale, color=YELLOW)
                        tex_label.set_stroke(BLACK, width=3.5, background=True)
                        dir = UP+RIGHT if x>=0 else UP+LEFT
                        tex_label.next_to(point, dir, buff=0.15*self.scale)
                        points_group.add(point, dashes, tex_label)
                    else:
                        points_group.add(point, dashes)
        except Exception as e:
            print(f"⚠️  Custom point drawing warning: {e}")
        return points_group

    def get_variable_animations(self) -> Tuple[List[Animation], float]:
        anims = []
        max_rt = 0.0
        for k, t in self.trackers.items():
            info = self.variables_info.get(k, {})
            if "end" in info and info["end"] != info.get("start", ""):
                rt = info.get("run_time", 3.0)
                max_rt = max(max_rt, rt)
                anims.append(t.animate.set_value(info["end"]))
        for item in self.moving_axis_trackers:
            rt = item["run_time"]
            max_rt = max(max_rt, rt)
        anims.extend(self.moving_axis_animations)
        for item in self.moving_func_trackers:
            rt = item["run_time"]
            max_rt = max(max_rt, rt)
        anims.extend(self.moving_func_animations)
        return anims, max_rt

def create_dynamic_functions(
    axes: Axes,
    graph_info_list: List[Dict],
    scale: float = 1.0,
) -> Tuple[List[Mobject], List[DynamicFunction], List[Mobject]]:
    if not axes:
        print("❌ Error: No coordinate axes, no rendering allowed!")
        return [], [], []
    if not isinstance(graph_info_list, list):
        graph_info_list = [graph_info_list]
    graphs = []
    dyn_funcs = []
    decorations = []
    for graph_info in graph_info_list:
        function_str = graph_info.get('function', '')
        if not function_str:
            continue
        variables = graph_info.get('variables', {})
        x_range = tuple(graph_info.get('x_range', [-5, 5]))
        color = graph_info.get('color', BLUE)
        show_axis_intersections = graph_info.get('show_axis_intersections', True)
        function_points = graph_info.get('function_points', [])
        moving_axis_point = graph_info.get('moving_axis_point', [])
        moving_function_point = graph_info.get('moving_function_point', [])
        
        dyn_func = DynamicFunction(
            axes=axes,
            function_str=function_str,
            variables=variables,
            x_range=x_range,
            color=color,
            scale=scale,
            show_axis_intersections=show_axis_intersections,
            function_points=function_points,
            moving_axis_point=moving_axis_point,
            moving_function_point=moving_function_point
        )
        graphs.append(dyn_func.graph)
        dyn_funcs.append(dyn_func)
        
        if show_axis_intersections:
            decorations.append(always_redraw(dyn_func.create_axis_intersections))
        if function_points:
            decorations.append(always_redraw(dyn_func.create_custom_points))
        if moving_axis_point:
            decorations.append(dyn_func.moving_axis_group)
        if moving_function_point:
            decorations.append(dyn_func.moving_func_group)
    return graphs, dyn_funcs, decorations

def create_function_intersections(dyn_funcs, axes, scale):
    if len(dyn_funcs) < 2:
        return None
    inter_group = VGroup()
    def update():
        g = VGroup()
        for i in range(len(dyn_funcs)):
            for j in range(i+1, len(dyn_funcs)):
                f1 = dyn_funcs[i].evaluate
                f2 = dyn_funcs[j].evaluate
                xmin = max(dyn_funcs[i].x_range[0], dyn_funcs[j].x_range[0])
                xmax = min(dyn_funcs[i].x_range[1], dyn_funcs[j].x_range[1])
                if xmin >= xmax:
                    continue
                def diff(x): return f1(x)-f2(x)
                roots = find_roots(diff, axes.x_range[0], axes.x_range[1])
                for x in roots:
                    y = f1(x)
                    if axes.y_range[0] <= y <= axes.y_range[1]:
                        dot = Dot(axes.c2p(x,y), radius=0.07*scale, color=YELLOW)
                        dot.set_stroke(BLACK, 2.5, True)
                        dash = create_coord_dashes(axes, x, y, scale)
                        g.add(dot, dash)
        inter_group.remove(*inter_group.submobjects)
        inter_group.add(g)
        return inter_group
    return always_redraw(update)

# ==========================
# Formula manager
# ==========================
class FormulaManager:
    def __init__(self, scene, base_position, max_formulas=3, spacing=0.8, font_size=25):
        self.scene = scene
        self.base_position = base_position
        self.max_formulas = max_formulas
        self.spacing = spacing
        self.font_size = font_size
        self.formulas = []
    def add_formula(self, tex):
        new = safe_math_tex(tex, font_size=self.font_size)
        if len(self.formulas)>=self.max_formulas:
            self.scene.play(*[FadeOut(f) for f in self.formulas], run_time=0.5)
            self.formulas.clear()
            new.shift(self.base_position)
        else:
            if self.formulas:
                self.scene.play(*[f.animate.shift(UP*self.spacing) for f in self.formulas], run_time=0.4)
            ny = self.base_position[1] - self.spacing * len(self.formulas)
            new.shift([self.base_position[0], ny, 0])
        self.scene.play(Write(new), run_time=1.2)
        self.formulas.append(new)
    def transform_last(self, tex):
        if not self.formulas:
            self.add_formula(tex)
            return
        new = safe_math_tex(tex, font_size=self.font_size)
        new.move_to(self.formulas[-1].get_center())
        self.scene.play(TransformMatchingShapes(self.formulas[-1], new), run_time=1.5)
        self.formulas[-1] = new
    def clear(self):
        if self.formulas:
            self.scene.play(*[FadeOut(f) for f in self.formulas], run_time=0.5)
            self.formulas.clear()

# ==========================
# New core module: JSON export independent Manim script
# ==========================
def export_manim_script(json_path, out_dir="export_manim"):
    """
    Read JSON, generate independent py rendering files for each graph_step, 
    completely solves image coverage issues
    :param json_path: input json path
    :param out_dir: output script folder
    """
    data = load_math_data(json_path)
    if not data:
        print("JSON parsing failed, cannot export")
        return
    os.makedirs(out_dir, exist_ok=True)
    steps = data.get("solve_steps", [])
    title_all = data.get("title", "Function image")
    init_formula = data.get("iner", "")
    base_header = '''# -*- coding: utf-8 -*-
from manim import *
import math
config.frame_rate=30
config.pixel_width=1920
config.pixel_height=1080

def create_coord_dashes(axes,x,y,scale):
    dash_style={"color":GRAY,"stroke_width":1.5*scale}
    g=VGroup()
    eps=1e-9
    fs=22*scale
    if abs(y)>eps:
        g.add(DashedLine(axes.c2p(x,y),axes.c2p(x,0),**dash_style))
    if abs(x)>eps:
        lt=MathTex(f"{x:.2f}",font_size=fs,color=YELLOW)
        lt.set_stroke(BLACK,3.5,True)
        lt.next_to(axes.c2p(x,0),DOWN if y>=0 else UP,buff=0.18*scale)
        g.add(lt)
    if abs(x)>eps:
        g.add(DashedLine(axes.c2p(x,y),axes.c2p(0,y),**dash_style))
    if abs(y)>eps:
        lt=MathTex(f"{y:.2f}",font_size=fs,color=YELLOW)
        lt.set_stroke(BLACK,3.5,True)
        lt.next_to(axes.c2p(0,y),LEFT if x>=0 else RIGHT,buff=0.18*scale)
        g.add(lt)
    return g

class SingleGraphScene(Scene):
    GLOBAL_SCALE=0.6
    def construct(self):
'''
    for idx, step in enumerate(steps):
        step_type = step.get("step_type")
        if step_type != "graph_step":
            continue
        step_name = step.get("step_name", f"Step{idx+1}")
        graph_list = step.get("graph", [])
        fade_out = step.get("fade_out", True)
        script_name = f"step_{idx+1}_{step_name}.py"
        script_path = os.path.join(out_dir, script_name)
        scene_lines = []

        scene_lines.append(f'        title=Text("{title_all}",font_size=20).shift(UP*3+LEFT*4)')
        if init_formula:
            scene_lines.append(f'        init_tex=MathTex("{init_formula}",font_size=25).shift(UP*2+LEFT*2)')
            scene_lines.append('        self.play(Write(title),Write(init_tex),run_time=1.2)')
        else:
            scene_lines.append('        self.play(Write(title),run_time=1.2)')
        scene_lines.append('        self.wait(1.5)')
        scene_lines.append('        self.play(FadeOut(title),run_time=0.8)')
        scene_lines.append('        self.wait(0.5)')

        all_xr, all_yr = [], []
        for g_info in graph_list:
            fx = g_info.get("function")
            x_rg = g_info.get("x_range",[-5,5])
            vars_cfg = g_info.get("variables",{})
            var_start = {k:v["start"] for k,v in vars_cfg.items()}
            def static_func(x):
                loc=dict(var_start)
                return eval(fx, {"math":math, "abs":abs, "sin":math.sin, "cos":math.cos, "tan":math.tan, "sqrt":math.sqrt}, loc)
            xs, ys = [],[]
            st=(x_rg[1]-x_rg[0])/1500
            for i in range(1501):
                xv=x_rg[0]+i*st
                try:yv=static_func(xv);xs.append(xv);ys.append(yv)
                except:pass
            if xs:
                all_xr.append((min(xs),max(xs)))
                all_yr.append((min(ys),max(ys)))
        min_x = min(i[0] for i in all_xr) if all_xr else -5
        max_x = max(i[1] for i in all_xr) if all_xr else 5
        min_y = min(i[0] for i in all_yr) if all_yr else -5
        max_y = max(i[1] for i in all_yr) if all_yr else 5
        if min_y>0:min_y=0
        if max_y<0:max_y=0
        x_step=1 if (max_x-min_x)<10 else 5
        y_step=1 if (max_y-min_y)<10 else 5

        scene_lines.append(f'        axes=Axes(x_range=[{min_x},{max_x},{x_step}],y_range=[{min_y},{max_y},{y_step}],x_length=7*self.GLOBAL_SCALE,y_length=7*self.GLOBAL_SCALE,axis_config={{"include_tip":True,"tick_size":0.05*self.GLOBAL_SCALE}}).move_to(RIGHT*4)')
        scene_lines.append('        xlab=MathTex("x").next_to(axes.get_x_axis(),RIGHT)')
        scene_lines.append('        ylab=MathTex("y").next_to(axes.get_y_axis(),UP)')
        scene_lines.append('        self.play(Create(axes),Write(VGroup(xlab,ylab)),run_time=1.0)')
        scene_lines.append('        self.wait(0.3)')

        for g_info in graph_list:
            func_str = g_info["function"]
            color = g_info.get("color", BLUE)
            x_rg = g_info.get("x_range",[-5,5])
            var_cfg = g_info.get("variables",{})
            move_axis = g_info.get("moving_axis_point",[])
            move_func = g_info.get("moving_function_point",[])
            static_pts = g_info.get("function_points",[])
            show_inter = g_info.get("show_axis_intersections",True)

            var_code = ",".join([f"{k}={v['start']}" for k,v in var_cfg.items()])
            scene_lines.append(f'        # Function {func_str}')
            scene_lines.append(f'        def f(x):')
            scene_lines.append(f'            {var_code}')
            scene_lines.append(f'            return eval("{func_str}", dict(math=math,abs=abs,sin=math.sin,cos=math.cos,tan=math.tan,sqrt=math.sqrt), locals())')

            scene_lines.append(f'        graph=axes.plot(f,x_range=[{x_rg[0]},{x_rg[1]}],stroke_width=2*self.GLOBAL_SCALE,color={repr(color)})')
            scene_lines.append('        self.play(Create(graph),run_time=1.0)')

            if show_inter:
                scene_lines.append('        inter_g=VGroup()')
                scene_lines.append('        def find_zero(f,xmin,xmax,step=0.0001):')
                scene_lines.append('            zs=[]')
                scene_lines.append('            prev=f(xmin)')
                scene_lines.append('            x=xmin+step')
                scene_lines.append('            while x<=xmax:')
                scene_lines.append('                curr=f(x)')
                scene_lines.append('                if prev*curr<=0 or abs(curr)<1e-9:')
                scene_lines.append('                    zs.append(x)')
                scene_lines.append('                prev=curr;x+=step')
                scene_lines.append('            return zs')
                scene_lines.append(f'        zeros=find_zero(f,{x_rg[0]},{x_rg[1]})')
                scene_lines.append('        for z in zeros:')
                scene_lines.append('            d=Dot(axes.c2p(z,0),radius=0.07*self.GLOBAL_SCALE,color=YELLOW)')
                scene_lines.append('            d.set_stroke(BLACK,2.5,True)')
                scene_lines.append('            inter_g.add(d,create_coord_dashes(axes,z,0,self.GLOBAL_SCALE))')
                scene_lines.append('        y0=f(0)')
                scene_lines.append('        dy=Dot(axes.c2p(0,y0),radius=0.07*self.GLOBAL_SCALE,color=YELLOW)')
                scene_lines.append('        dy.set_stroke(BLACK,2.5,True)')
                scene_lines.append('        inter_g.add(dy,create_coord_dashes(axes,0,y0,self.GLOBAL_SCALE))')
                scene_lines.append('        self.play(Create(inter_g),run_time=0.6)')

            if static_pts:
                scene_lines.append('        static_pt_g=VGroup()')
                for p in static_pts:
                    px=p["x"]
                    plabel=p.get("label","")
                    scene_lines.append(f'        py=f({px})')
                    scene_lines.append(f'        dp=Dot(axes.c2p({px},py),radius=0.07*self.GLOBAL_SCALE,color=YELLOW)')
                    scene_lines.append('        dp.set_stroke(BLACK,2.5,True)')
                    scene_lines.append(f'        ptv=VGroup(dp,create_coord_dashes(axes,{px},py,self.GLOBAL_SCALE))')
                    if plabel:
                        scene_lines.append(f'        lab=MathTex("{plabel}",font_size=24*self.GLOBAL_SCALE,color=YELLOW).set_stroke(BLACK,3.5,True)')
                        scene_lines.append(f'        lab.next_to(dp,UP+RIGHT if {px}>=0 else UP+LEFT,buff=0.15*self.GLOBAL_SCALE)')
                        scene_lines.append('        ptv.add(lab)')
                    scene_lines.append('        static_pt_g.add(ptv)')
                scene_lines.append('        self.play(Create(static_pt_g), run_time=0.6)')

            if move_axis:
                for mp in move_axis:
                    ax=mp["axis"]
                    s=mp["start"]
                    e=mp["end"]
                    rt=mp["run_time"]
                    lab=mp.get("label","")
                    if ax=="x":
                        scene_lines.append(f'        t_axis=ValueTracker({s})')
                        scene_lines.append('        def upd_axis(mobj):')
                        scene_lines.append('            xv=t_axis.get_value()')
                        scene_lines.append('            g=VGroup()')
                        scene_lines.append('            d=Dot(axes.c2p(xv,0),radius=0.07*self.GLOBAL_SCALE,color=YELLOW).set_stroke(BLACK,2.5,True)')
                        scene_lines.append('            g.add(d,create_coord_dashes(axes,xv,0,self.GLOBAL_SCALE))')
                        if lab:
                            scene_lines.append(f'            l=MathTex("{lab}",font_size=24*self.GLOBAL_SCALE,color=YELLOW).set_stroke(BLACK,3.5,True).next_to(d,UP,buff=0.12)')
                            scene_lines.append('            g.add(l)')
                        scene_lines.append('            mobj.become(g)')
                        scene_lines.append('        axis_mov=always_redraw(VGroup()).add_updater(upd_axis)')
                        scene_lines.append('        self.add(axis_mov)')
                        scene_lines.append(f'        self.play(t_axis.animate.set_value({e}),run_time={rt})')

            if move_func:
                for mfp in move_func:
                    xs=mfp["x_start"]
                    xe=mfp["x_end"]
                    rt=mfp["run_time"]
                    lab=mfp.get("label","")
                    scene_lines.append(f'        t_func=ValueTracker({xs})')
                    scene_lines.append('        def upd_func(mobj):')
                    scene_lines.append('            xv=t_func.get_value()')
                    scene_lines.append('            yv=f(xv)')
                    scene_lines.append('            g=VGroup()')
                    scene_lines.append('            d=Dot(axes.c2p(xv,yv),radius=0.07*self.GLOBAL_SCALE,color=YELLOW).set_stroke(BLACK,2.5,True)')
                    scene_lines.append('            g.add(d,create_coord_dashes(axes,xv,yv,self.GLOBAL_SCALE))')
                    if lab:
                        scene_lines.append(f'            l=MathTex("{lab}",font_size=24*self.GLOBAL_SCALE,color=YELLOW).set_stroke(BLACK,3.5,True).next_to(d,UP+RIGHT if xv>=0 else UP+LEFT,buff=0.12)')
                        scene_lines.append('            g.add(l)')
                    scene_lines.append('            mobj.become(g)')
                    scene_lines.append('        func_mov=always_redraw(VGroup()).add_updater(upd_func)')
                    scene_lines.append('        self.add(func_mov)')
                    scene_lines.append(f'        self.play(t_func.animate.set_value({xe}),run_time={rt})')

        if fade_out:
            scene_lines.append('        self.wait(1.5)')
            scene_lines.append('        self.play(FadeOut(graph), FadeOut(inter_g), run_time=0.4)')
        scene_lines.append("        self.wait(4)")
        scene_lines.append("if __name__=='__main__':")
        scene_lines.append("    scene=SingleGraphScene()")
        scene_lines.append("    scene.render()")

        full_script = base_header + "\n".join(scene_lines)
        with open(script_path,"w",encoding="utf-8") as f:
            f.write(full_script)
        print(f"Exported independent rendering script: {script_path}")
    print(f"\nExport complete! All sub-step scripts stored in: {out_dir}")

# ==========================
# Main scene class
# ==========================
class SolveEquation(Scene):
    GLOBAL_SCALE = 0.6
    TARGET_Y_RANGE = (-6, 6)
    MAX_FORMULAS = 3
    FORMULA_SPACING = 0.8
    BASE_POSITION = UP * 2 + LEFT * 2
    TITLE_FONT_SIZE = 20
    FORMULA_FONT_SIZE = 25
    def __init__(self, json_path="func.json", performance_mode="balanced",**kwargs):
        super().__init__(**kwargs)
        self.json_path = json_path
        self.performance_mode = performance_mode
        global PERFORMANCE_MODE, _PERF_CACHE
        PERFORMANCE_MODE = performance_mode
        _PERF_CACHE.clear()
        self.axes = None
        self.axes_labels = None
        self.has_axes = False
        self.last_graphs = []
        self.formula_mgr = None
    def construct(self):
        hw_enabled, hw_msg = setup_hardware_acceleration()
        perf_info = get_performance_settings()
        print(f"⚡ Performance mode: {perf_info['description']}")
        print(f"🖥️{hw_msg}")
        data = load_math_data(self.json_path)
        if not data:
            print("❌ Cannot load JSON")
            return
        self.formula_mgr = FormulaManager(self, self.BASE_POSITION, self.MAX_FORMULAS, self.FORMULA_SPACING, self.FORMULA_FONT_SIZE)
        title = Text(data.get("title", "Math"), font_size=self.TITLE_FONT_SIZE).shift(UP*3+LEFT*4)
        init_content = data.get("iner", "")
        if init_content:
            init_text = safe_math_tex(init_content, font_size=self.FORMULA_FONT_SIZE).shift(self.BASE_POSITION)
            self.play(Write(title), Write(init_text), run_time=1.2)
            self.formula_mgr.formulas.append(init_text)
        else:
            self.play(Write(title), run_time=1.2)
        self.wait(1.5)
        self.play(FadeOut(title), run_time=0.8)
        self.wait(1)
        steps = data.get("solve_steps", [])
        print(f"Total {len(steps)} steps")
        for idx, step in enumerate(steps):
            print(f"Executing step{idx+1}")
            self._execute_step(idx, step)
        print("✅ Rendering complete")
        self.wait(4)
    def _execute_step(self, idx, step):
        step_type = step.get("step_type", "normal")
        need_axes = step_type == "graph_step"
        fade_out = step.get("fade_out", True)
        if need_axes and not self.has_axes:
            self._create_axes(step.get("graph", []))
        elif not need_axes and self.has_axes:
            self._destroy_axes()
        graphs, dyn_funcs = [], []
        if need_axes and self.has_axes:
            graphs, dyn_funcs = self._render_graph(step)
        self._render_text(step)
        if need_axes and dyn_funcs:
            all_anims = []
            max_rt = 0.0
            for df in dyn_funcs:
                anim_list, rt = df.get_variable_animations()
                all_anims.extend(anim_list)
                max_rt = max(max_rt, rt)
            if all_anims:
                self.play(*all_anims, run_time=max_rt)
                self.wait(1.2)
        if step_type == "graph_step" and self.last_graphs and fade_out:
            self.wait(1.5)
            self.play(*[FadeOut(g) for g in self.last_graphs], run_time=0.4)
            self.last_graphs.clear()
            self.wait(0.3)
    def _create_axes(self, graph_data):
        graph_list = graph_data if isinstance(graph_data, list) else [graph_data]
        all_xr, all_yr = [], []
        for gi in graph_list:
            f_str = gi.get("function", "")
            if not f_str:
                continue
            xr = tuple(gi.get("x_range",[-5,5]))
            vars_dict = gi.get("variables",{})
            v_names = ["x"]+list(vars_dict.keys())
            starts = [v["start"] for v in vars_dict.values()]
            sf = create_safe_function(f_str, v_names)
            def sfx(x):return sf(x,*starts)
            sx, sy = calculate_smart_ranges(sfx, xr, self.TARGET_Y_RANGE)
            all_xr.append(sx)
            all_yr.append(sy)
        minx = min(x[0] for x in all_xr) if all_xr else -5
        maxx = max(x[1] for x in all_xr) if all_xr else 5
        miny = min(y[0] for y in all_yr) if all_yr else -5
        maxy = max(y[1] for y in all_yr) if all_yr else 5
        if miny > 0: miny = 0
        if maxy < 0: maxy = 0
        xstep = 1 if (maxx-minx)<10 else 5
        ystep = 1 if (maxy-miny)<10 else 5
        self.axes = Axes(
            x_range=[minx, maxx, xstep],
            y_range=[miny, maxy, ystep],
            x_length=7*self.GLOBAL_SCALE,
            y_length=7*self.GLOBAL_SCALE,
            axis_config={"include_tip":True, "tip_width":0.1*self.GLOBAL_SCALE, "tick_size":0.05*self.GLOBAL_SCALE}
        ).move_to(RIGHT*4)
        xlab = MathTex("x").next_to(self.axes.get_x_axis(), RIGHT)
        ylab = MathTex("y").next_to(self.axes.get_y_axis(), UP)
        self.axes_labels = VGroup(xlab, ylab)
        self.play(Create(self.axes), Write(self.axes_labels), run_time=1.0)
        self.has_axes = True
        self.wait(0.5)
    def _destroy_axes(self):
        if self.last_graphs:
            self.play(*[FadeOut(g) for g in self.last_graphs], run_time=0.4)
            self.last_graphs.clear()
        self.play(FadeOut(self.axes), FadeOut(self.axes_labels), run_time=0.6)
        self.axes = None
        self.axes_labels = None
        self.has_axes = False
        self.wait(0.3)
    def _render_graph(self, step):
        gdata = step.get("graph")
        if not gdata:
            return [], []
        if step.get("clear_graph", True) and self.last_graphs:
            self.play(*[FadeOut(g) for g in self.last_graphs], run_time=0.4)
            self.last_graphs.clear()
        graphs, dyn_funcs, dec = create_dynamic_functions(self.axes, gdata, self.GLOBAL_SCALE)
        all_ele = graphs + dec
        if len(dyn_funcs)>=2 and step.get("show_function_intersections", True):
            inter = create_function_intersections(dyn_funcs, self.axes, self.GLOBAL_SCALE)
            if inter:
                all_ele.append(inter)
        if all_ele:
            self.play(*[Create(e) for e in all_ele], run_time=1.2)
            self.last_graphs = all_ele
        return all_ele, dyn_funcs
    def _render_text(self, step):
        title_txt = step.get("step_name", "") or step.get("oper_type", "")
        detail_txt = step.get("step_detail", "") or step.get("purpose", "")
        title_obj = None
        detail_obj = None
        anims = []
        if title_txt:
            title_obj = Text(title_txt, font_size=self.TITLE_FONT_SIZE).shift(UP*3+LEFT*4.5)
            anims.append(Write(title_obj))
        if detail_txt:
            detail_obj = Text(detail_txt, font_size=self.TITLE_FONT_SIZE).shift(LEFT*2)
            anims.append(Write(detail_obj))
        if anims:
            self.play(*anims, run_time=0.7)
        cont = step.get("content", "")
        alg = step.get("algebraic_expression", "")
        if step.get("step_type") == "simplify":
            if cont:
                self.formula_mgr.transform_last(cont)
            self.wait(1.2)
        else:
            f_cont = cont if cont else alg
            if f_cont:
                self.formula_mgr.add_formula(f_cont)
            self.wait(1.0)
        fade = []
        if title_obj: fade.append(FadeOut(title_obj))
        if detail_obj: fade.append(FadeOut(detail_obj))
        if fade:
            self.play(*fade, run_time=0.6)

# ==========================
# Command-line interface
# ==========================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Algebraic visualization | Supports JSON export to independent Manim scripts, solves image overlay issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Use --export to output independent Manim scripts, render separately without layer conflicts"
    )
    parser.add_argument("json_file", nargs="?", default="aaa.json")
    parser.add_argument("-o", "--output")
    parser.add_argument("-q", "--quality", default="medium_quality", choices=["low_quality","medium_quality","high_quality","fourk_quality"])
    parser.add_argument("-p", "--performance", default="balanced", choices=["quality","balanced","speed","ultra_fast"])
    parser.add_argument("--export", action="store_true", help="Only export independent Manim scripts, no video rendering")
    parser.add_argument("--export-dir", default="export_manim", help="Export directory")
    parser.add_argument("--no-hw-accel", action="store_true")
    args = parser.parse_args()
    config.quality = args.quality
    if args.no_hw_accel:
        HW_ACCEL_DISABLED = True
    if args.export:
        export_manim_script(args.json_file, args.export_dir)
        sys.exit(0)
    scene = SolveEquation(json_path=args.json_file, performance_mode=args.performance)
    scene.render()
