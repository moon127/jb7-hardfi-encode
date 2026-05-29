from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from hardfi_encode.converter import (
    plan_conversion,
    run_conversion,
    verify_ffmpeg,
)
from hardfi_encode.models import (
    CodecType,
    is_lossless,
)
from hardfi_encode.scanner import (
    find_search_root,
    get_bitrate_range,
    scan_directory,
)

logger = logging.getLogger(__name__)

CODEC_DISPLAY_ORDER = [CodecType.WAV, CodecType.FLAC, CodecType.ALAC, CodecType.AAC, CodecType.MP3, CodecType.UNKNOWN]

BITRATE_OPTIONS = {
    "128k": 128000,
    "192k": 192000,
    "256k": 256000,
    "320k": 320000,
}


class HardfiEncoderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("JB7 HardFi Encode")
        self.root.minsize(700, 500)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.source_dir: str | None = None
        self.target_dir: str | None = None
        self.scan_result = None
        self.converting = False
        self._cancel_requested = False
        self._start_time: float | None = None
        self._albums: dict[str, list] = {}
        self._album_filter: set[str] | None = None
        self.source_type_var = tk.StringVar(value="lossless")
        self.source_type_label: ttk.Label | None = None

        self._build_ui()

        if not verify_ffmpeg():
            messagebox.showwarning(
                "ffmpeg Not Found",
                "ffmpeg was not found on your system. "
                "Conversion will not work.\n\n"
                "Install ffmpeg:\n"
                "  macOS: brew install ffmpeg\n"
                "  Windows: choco install ffmpeg  (or download from ffmpeg.org)",
            )

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding="10")
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        self._build_dir_frame(main)
        self._build_target_dir_frame(main)
        self._build_summary_frame(main)
        self._build_options_frame(main)
        self._build_progress_frame(main)

    def _build_dir_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Source Directory", padding="5")
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        ttk.Button(frame, text="Select Source", command=self._select_directory).grid(row=0, column=0, padx=(0, 5))
        self.dir_label = ttk.Label(frame, text="No directory selected")
        self.dir_label.grid(row=0, column=1, sticky="w")

    def _build_target_dir_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Output Directory (optional)", padding="5")
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        ttk.Button(frame, text="Select Output", command=self._select_target_directory).grid(row=0, column=0, padx=(0, 5))
        self.target_dir_label = ttk.Label(frame, text="Encode in place (same as source)")
        self.target_dir_label.grid(row=0, column=1, sticky="w")
        self.clear_target_btn = ttk.Button(frame, text="Clear", command=self._clear_target_directory, state="disabled")
        self.clear_target_btn.grid(row=0, column=2, padx=(5, 0))

    def _build_summary_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Audio Summary", padding="5")
        frame.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        self.total_label = ttk.Label(frame, text="")
        self.total_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        cols = ("codec", "count", "bitrate", "compressible")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=6)
        self.tree.heading("codec", text="Codec")
        self.tree.heading("count", text="Count")
        self.tree.heading("bitrate", text="Bitrate")
        self.tree.heading("compressible", text="Compressible")

        self.tree.column("codec", width=80)
        self.tree.column("count", width=70, anchor="center")
        self.tree.column("bitrate", width=120, anchor="center")
        self.tree.column("compressible", width=100, anchor="center")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

    def _build_options_frame(self, parent: ttk.Frame) -> None:
        self.options_frame = ttk.LabelFrame(parent, text="Conversion Options", padding="10")
        self.options_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        self.options_frame.columnconfigure(0, weight=1)
        self.options_frame.columnconfigure(1, weight=1)

        source_frame = ttk.Frame(self.options_frame)
        source_frame.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(source_frame, text="Convert from:").grid(row=0, column=0, padx=(0, 10), sticky="w")
        self.source_type_var = tk.StringVar(value="lossless")
        self.lossless_rb = ttk.Radiobutton(source_frame, text="Lossless (WAV, FLAC, ALAC)", variable=self.source_type_var, value="lossless", command=self._on_source_change)
        self.aac_rb = ttk.Radiobutton(source_frame, text="AAC", variable=self.source_type_var, value="aac", command=self._on_source_change)
        self.all_rb = ttk.Radiobutton(source_frame, text="All", variable=self.source_type_var, value="all", command=self._on_source_change)
        self.lossless_rb.grid(row=0, column=1, padx=(0, 5))
        self.aac_rb.grid(row=0, column=2, padx=(0, 5))
        self.all_rb.grid(row=0, column=3)

        self.source_type_label = ttk.Label(source_frame, text="")
        self.source_type_label.grid(row=0, column=4, padx=(20, 0), sticky="w")

        self.convert_frame = ttk.Frame(self.options_frame)
        self.convert_frame.grid(row=1, column=0, columnspan=2, sticky="w")
        self.convert_frame.columnconfigure(1, weight=1)

        ttk.Label(self.convert_frame, text="Target format:").grid(row=0, column=0, padx=(0, 10), sticky="w")
        self.target_var = tk.StringVar(value="")
        self.wav_rb = ttk.Radiobutton(self.convert_frame, text="WAV (lossless)", variable=self.target_var, value="WAV", command=self._on_target_change)
        self.flac_rb = ttk.Radiobutton(self.convert_frame, text="FLAC (lossless)", variable=self.target_var, value="FLAC", command=self._on_target_change)
        self.aac_rb = ttk.Radiobutton(self.convert_frame, text="AAC", variable=self.target_var, value="AAC", command=self._on_target_change)
        self.mp3_rb = ttk.Radiobutton(self.convert_frame, text="MP3", variable=self.target_var, value="MP3", command=self._on_target_change)

        self.wav_rb.grid(row=0, column=1, padx=(0, 5))
        self.flac_rb.grid(row=0, column=2, padx=(0, 5))
        self.aac_rb.grid(row=0, column=3, padx=(0, 5))
        self.mp3_rb.grid(row=0, column=4)

        self.bitrate_label = ttk.Label(self.convert_frame, text="Bitrate:")
        self.bitrate_var = tk.StringVar(value="192k")
        self.bitrate_combo = ttk.Combobox(
            self.convert_frame, textvariable=self.bitrate_var,
            values=list(BITRATE_OPTIONS.keys()), state="readonly", width=10,
        )
        self.bitrate_label.grid(row=1, column=0, padx=(0, 10), pady=(8, 0), sticky="w")
        self.bitrate_combo.grid(row=1, column=1, padx=(0, 5), pady=(8, 0), sticky="w")
        self.bitrate_label.grid_remove()
        self.bitrate_combo.grid_remove()

        ttk.Label(self.convert_frame, text="").grid(row=2, column=0)

        self.delete_var = tk.BooleanVar(value=False)
        self.delete_cb = ttk.Checkbutton(
            self.convert_frame, text="Delete original files after conversion",
            variable=self.delete_var, command=self._on_delete_toggle,
        )
        self.delete_cb.grid(row=3, column=0, columnspan=4, sticky="w")

        self._album_label_var = tk.StringVar(value="")
        self._album_label = ttk.Label(self.options_frame, textvariable=self._album_label_var)
        self._album_label.grid(row=2, column=0, columnspan=2, pady=(0, 5))
        self._album_label.grid_remove()

        action_frame = ttk.Frame(self.options_frame)
        action_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))

        self.convert_btn = ttk.Button(
            action_frame, text="Start Conversion",
            command=self._start_conversion, state="disabled",
        )
        self.convert_btn.grid(row=0, column=0, padx=(0, 10))

        self.album_btn = ttk.Button(
            action_frame, text="Choose Albums\u2026",
            command=self._show_album_selector, state="disabled",
        )
        self.album_btn.grid(row=0, column=1)

    def _build_progress_frame(self, parent: ttk.Frame) -> None:
        self.progress_frame = ttk.Frame(parent)
        self.progress_frame.grid(row=4, column=0, sticky="ew")
        self.progress_frame.columnconfigure(1, weight=1)

        self.progress_bar = ttk.Progressbar(self.progress_frame, mode="determinate")
        self.progress_label = ttk.Label(self.progress_frame, text="")
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.progress_label.grid(row=0, column=1, sticky="w")

        self.progress_frame.grid_remove()

    def _on_target_change(self) -> None:
        target = self.target_var.get()
        if target in ("AAC", "MP3"):
            self.bitrate_label.grid()
            self.bitrate_combo.grid()
        else:
            self.bitrate_label.grid_remove()
            self.bitrate_combo.grid_remove()

    def _on_source_change(self) -> None:
        if not self.scan_result:
            return
        source_type = self.source_type_var.get()
        count = self._count_source_files(source_type)
        if count > 0:
            self.convert_btn.configure(state="normal")
            if not self.target_var.get():
                self.target_var.set("FLAC" if source_type == "lossless" else "MP3")
        else:
            self.convert_btn.configure(state="disabled")
        self._update_source_count_label()

    def _matches_source_type(self, codec: CodecType, source_type: str) -> bool:
        if source_type == "aac":
            return codec == CodecType.AAC
        if source_type == "all":
            return is_lossless(codec) or codec == CodecType.AAC
        return is_lossless(codec)

    def _count_source_files(self, source_type: str) -> int:
        if not self.scan_result:
            return 0
        if source_type == "aac":
            return len(self.scan_result.by_codec.get(CodecType.AAC, []))
        if source_type == "all":
            return sum(len(v) for k, v in self.scan_result.by_codec.items() if is_lossless(k) or k == CodecType.AAC)
        return sum(len(v) for k, v in self.scan_result.by_codec.items() if is_lossless(k))

    def _update_source_count_label(self) -> None:
        if not self.scan_result or self.source_type_label is None:
            return
        source_type = self.source_type_var.get()
        count = self._count_source_files(source_type)
        labels = {"lossless": "lossless", "aac": "AAC", "all": "lossless + AAC"}
        self.source_type_label.configure(text=f"Files matching: {count} ({labels.get(source_type, '')})")

    def _on_delete_toggle(self) -> None:
        if self.delete_var.get():
            confirm = messagebox.askyesno(
                "Confirm Deletion",
                "WARNING: Original source files will be permanently deleted.\n\n"
                "This action cannot be undone. Are you sure?",
                icon="warning",
            )
            if not confirm:
                self.delete_var.set(False)

    def _select_directory(self) -> None:
        dir_path = filedialog.askdirectory(title="Select Source Directory")
        if not dir_path:
            return

        self.source_dir = dir_path
        self.dir_label.configure(text=dir_path)
        self.target_dir = None
        self.target_dir_label.configure(text="Encode in place (same as source)")
        self.clear_target_btn.configure(state="disabled")
        self.scan_result = None
        self._albums = {}
        self._album_filter = None
        self._album_label.grid_remove()
        self.convert_btn.configure(state="disabled")
        self.album_btn.configure(state="disabled")

        self._clear_summary()

        threading.Thread(target=self._run_scan, daemon=True).start()

    def _select_target_directory(self) -> None:
        dir_path = filedialog.askdirectory(title="Select Output Directory")
        if not dir_path:
            return
        self.target_dir = dir_path
        self.target_dir_label.configure(text=dir_path)
        self.clear_target_btn.configure(state="normal")
        self.delete_var.set(False)
        self.delete_cb.configure(state="disabled")

    def _clear_target_directory(self) -> None:
        self.target_dir = None
        self.target_dir_label.configure(text="Encode in place (same as source)")
        self.clear_target_btn.configure(state="disabled")
        if self.scan_result and any(
            is_lossless(k) for k in self.scan_result.by_codec
        ):
            self.delete_cb.configure(state="normal")

    def _clear_summary(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.total_label.configure(text="Scanning...")

    def _run_scan(self) -> None:
        try:
            from hardfi_encode.scanner import scan_directory
            result = scan_directory(Path(self.source_dir))
            self.root.after(0, self._on_scan_complete, result)
        except Exception as e:
            logger.exception("Scan failed")
            self.root.after(0, messagebox.showerror, "Scan Error", str(e))
            self.root.after(0, self.total_label.configure, {"text": "Scan failed"})

    def _on_scan_complete(self, result) -> None:
        self.scan_result = result
        self.total_label.configure(text=f"Total audio files found: {result.total_files}")

        for item in self.tree.get_children():
            self.tree.delete(item)

        for codec in CODEC_DISPLAY_ORDER:
            files = result.by_codec.get(codec, [])
            if not files:
                continue
            br = get_bitrate_range(files)
            comp = "Yes" if is_lossless(codec) else "No"
            self.tree.insert("", "end", values=(codec.value, len(files), br, comp))

        if result.total_files == 0:
            messagebox.showinfo("No Audio Files", "No supported audio files found in the selected directory.")
            self.album_btn.configure(state="disabled")
            return

        self._albums = self._get_albums(result.files)
        self._album_filter = None
        self._album_label.grid_remove()

        lossless_count = sum(len(v) for k, v in result.by_codec.items() if is_lossless(k))
        aac_count = len(result.by_codec.get(CodecType.AAC, []))

        self._enable_options()
        self.source_type_var.set("lossless")
        self._on_source_change()
        if self.target_dir:
            self.delete_var.set(False)
            self.delete_cb.configure(state="disabled")
        else:
            self.delete_cb.configure(state="normal")

        if lossless_count > 0:
            self.target_var.set("FLAC")
            self._on_target_change()
            self.convert_btn.configure(state="normal")
            self.album_btn.configure(state="normal")
        elif aac_count > 0:
            self.target_var.set("MP3")
            self._on_target_change()
            self.convert_btn.configure(state="normal")
            self.album_btn.configure(state="normal")
        else:
            self.convert_btn.configure(state="disabled")
            self.album_btn.configure(state="disabled")
            messagebox.showinfo(
                "Nothing to Convert",
                "No lossless or AAC files found to convert.",
            )

        self._update_source_count_label()

    def _get_albums(self, files) -> dict[str, list]:
        albums: dict[str, list] = {}
        for af in files:
            parent = str(Path(af.relative_path).parent)
            albums.setdefault(parent, []).append(af)
        return albums

    def _show_album_selector(self) -> None:
        if not self._albums:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Choose Albums to Convert")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.minsize(500, 300)

        ttk.Label(dialog, text="Select albums to include in conversion:", padding=(10, 10, 10, 5)).pack(fill="x")

        canvas = tk.Canvas(dialog, highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        source_type = self.source_type_var.get()
        vars: dict[str, tk.BooleanVar] = {}
        for album in sorted(self._albums):
            files = self._albums[album]
            matching = sum(1 for f in files if self._matches_source_type(f.codec, source_type))
            codecs = ", ".join(sorted(set(f.codec.value for f in files)))
            var = tk.BooleanVar(value=True)
            vars[album] = var
            cb = ttk.Checkbutton(
                scroll_frame, text=f"{album}  ({matching} files matching\u2014{codecs})",
                variable=var,
            )
            cb.pack(anchor="w", padx=10, pady=1)

        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
        scrollbar.pack(side="right", fill="y", pady=(0, 10))

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=(0, 10))

        def select_all():
            for v in vars.values():
                v.set(True)

        def deselect_all():
            for v in vars.values():
                v.set(False)

        def done(album_filter: set[str] | None):
            self._album_filter = album_filter
            if album_filter is not None:
                source_type = self.source_type_var.get()
                matching = sum(1 for a in album_filter for f in self._albums[a] if self._matches_source_type(f.codec, source_type))
                label = f"Albums selected: {len(album_filter)} ({matching} files matching)"
                self._album_label_var.set(label)
                self._album_label.grid()
            else:
                self._album_filter = None
                self._album_label.grid_remove()
            dialog.destroy()

        ttk.Button(btn_frame, text="Select All", command=select_all).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Deselect All", command=deselect_all).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Convert All", command=lambda: done(None)).grid(row=0, column=2, padx=5)
        ttk.Button(btn_frame, text="Convert Selected", command=lambda: done({a for a, v in vars.items() if v.get()})).grid(row=0, column=3, padx=5)

    def _enable_options(self) -> None:
        for child in self.convert_frame.winfo_children():
            if isinstance(child, (ttk.Radiobutton, ttk.Checkbutton, ttk.Combobox, ttk.Label)):
                child.configure(state="normal")
        for rb in (self.lossless_rb, self.aac_rb, self.all_rb):
            rb.configure(state="normal")

    def _disable_options(self) -> None:
        for child in self.convert_frame.winfo_children():
            if isinstance(child, (ttk.Radiobutton, ttk.Checkbutton, ttk.Combobox, ttk.Label)):
                child.configure(state="disabled")
        for rb in (self.lossless_rb, self.aac_rb, self.all_rb):
            rb.configure(state="disabled")

    def _start_conversion(self) -> None:
        if self.converting or not self.scan_result:
            return

        target_codec_str = self.target_var.get()
        if not target_codec_str:
            messagebox.showwarning("No Target", "Please select a target format.")
            return

        target_codec = CodecType[target_codec_str]
        bitrate = None
        if target_codec in (CodecType.AAC, CodecType.MP3):
            bitrate_label = self.bitrate_var.get()
            bitrate = BITRATE_OPTIONS.get(bitrate_label)
            if not bitrate:
                messagebox.showwarning("Invalid Bitrate", "Please select a valid bitrate.")
                return

        source_type = self.source_type_var.get()
        files = self.scan_result.files
        if self._album_filter is not None:
            files = [f for f in files if str(Path(f.relative_path).parent) in self._album_filter]

        plan = plan_conversion(
            files,
            target_codec=target_codec,
            bitrate=bitrate,
            delete_originals=self.delete_var.get(),
            source_type=source_type,
        )

        if not plan.files_to_convert:
            if source_type == "lossless":
                msg = "All lossless files are already in the target format."
            elif source_type == "aac":
                msg = "All AAC files are already in the target format."
            else:
                msg = "All convertible files are already in the target format."
            messagebox.showinfo("Nothing to Convert", msg)
            return

        count = len(plan.files_to_convert)
        msg = f"Convert {count} file(s) to {target_codec.value}?\n\n"
        if self.target_dir:
            msg += f"Output: {self.target_dir}\nOriginal files will be kept."
        else:
            msg += f"{'Original files will be DELETED.' if plan.delete_originals else 'Original files will be kept.'}"
        if not messagebox.askyesno("Confirm Conversion", msg):
            return

        self.converting = True
        self._cancel_requested = False
        self.convert_btn.configure(text="Cancel", command=self._cancel_conversion, state="normal")
        self.progress_frame.grid()
        self.progress_bar["value"] = 0
        self._start_time = time.monotonic()
        self.progress_label.configure(text="Starting...")

        threading.Thread(
            target=self._run_conversion_thread,
            args=(plan, self.scan_result.search_root),
            daemon=True,
        ).start()

    def _cancel_conversion(self) -> None:
        self._cancel_requested = True
        self.convert_btn.configure(state="disabled", text="Cancelling...")

    def _format_eta(self, remaining: float) -> str:
        if remaining < 1:
            return "< 1s remaining"
        if remaining < 60:
            return f"{int(remaining)}s remaining"
        if remaining < 3600:
            return f"{int(remaining // 60)}m {int(remaining % 60)}s remaining"
        return f"{int(remaining // 3600)}h {int((remaining % 3600) // 60)}m remaining"

    def _update_progress(self, pct: int, status: str) -> None:
        if self._start_time is not None and pct > 0:
            elapsed = time.monotonic() - self._start_time
            remaining = (elapsed / pct) * (100 - pct)
            status = f"{status} — {self._format_eta(remaining)}"
        self.root.after(0, self.progress_bar.configure, {"value": pct})
        self.root.after(0, self.progress_label.configure, {"text": status})

    def _run_conversion_thread(self, plan, search_root: str) -> None:
        try:
            results = run_conversion(
                plan, search_root,
                progress_callback=self._update_progress,
                cancel_check=lambda: self._cancel_requested,
                target_dir=self.target_dir,
            )
            self.root.after(0, self._on_conversion_done, results)
        except Exception as e:
            logger.exception("Conversion failed")
            self.root.after(0, messagebox.showerror, "Conversion Error", str(e))
            self.root.after(0, self._reset_after_conversion)

    def _on_conversion_done(self, results: dict) -> None:
        if results.get("cancelled"):
            messagebox.showinfo("Cancelled", "Conversion was cancelled.")
        else:
            msg = (
                f"Conversion complete!\n\n"
                f"Converted: {results['converted']}\n"
                f"Skipped:   {results['skipped']}\n"
                f"Errors:    {results['errors']}"
            )
            messagebox.showinfo("Conversion Complete", msg)
        self._reset_after_conversion()

    def _reset_after_conversion(self) -> None:
        self.converting = False
        self._cancel_requested = False
        self.convert_btn.configure(state="normal", text="Start Conversion", command=self._start_conversion)
        self.progress_frame.grid_remove()


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    root = tk.Tk()
    app = HardfiEncoderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
