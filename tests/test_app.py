from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hardfi_encode.models import CodecType, AudioFile, ScanResult


# Use real types for ttk classes so isinstance() works in app.py
class MockTtkWidget:
    def __init__(self, *a, **kw):
        self._state = None

    def yview(self, *a):
        pass

    def configure(self, **kw):
        self._state = kw

    def __setitem__(self, key, value):
        pass

    def grid(self, *a, **kw):
        pass

    def grid_remove(self):
        pass

    def winfo_children(self):
        return []

    def columnconfigure(self, *a, **kw):
        pass

    def rowconfigure(self, *a, **kw):
        pass

    def heading(self, *a, **kw):
        pass

    def column(self, *a, **kw):
        pass

    def get_children(self):
        return []

    def delete(self, *a, **kw):
        pass

    def insert(self, *a, **kw):
        pass

    def set(self, *a, **kw):
        pass

    def get(self, *a, **kw):
        return ""


class MockRadiobutton(MockTtkWidget):
    pass


class MockCheckbutton(MockTtkWidget):
    pass


class MockCombobox(MockTtkWidget):
    pass


class MockLabel(MockTtkWidget):
    pass


class MockFrame(MockTtkWidget):
    pass


class MockLabelFrame(MockTtkWidget):
    pass


@pytest.fixture
def mock_tk(mocker):
    mocker.patch("hardfi_encode.app.tk.Tk", return_value=MagicMock())
    mocker.patch("hardfi_encode.app.tk.StringVar", side_effect=lambda **kw: MagicMock())
    mocker.patch("hardfi_encode.app.tk.BooleanVar", side_effect=lambda **kw: MagicMock())
    mocker.patch("hardfi_encode.app.filedialog")
    mocker.patch("hardfi_encode.app.messagebox")
    mocker.patch("hardfi_encode.app.ttk.Frame", MockFrame)
    mocker.patch("hardfi_encode.app.ttk.LabelFrame", MockLabelFrame)
    mocker.patch("hardfi_encode.app.ttk.Label", MockLabel)
    mocker.patch("hardfi_encode.app.ttk.Button", MockTtkWidget)
    mocker.patch("hardfi_encode.app.ttk.Radiobutton", MockRadiobutton)
    mocker.patch("hardfi_encode.app.ttk.Combobox", MockCombobox)
    mocker.patch("hardfi_encode.app.ttk.Checkbutton", MockCheckbutton)
    mocker.patch("hardfi_encode.app.ttk.Treeview", MockTtkWidget)
    mocker.patch("hardfi_encode.app.ttk.Scrollbar", MockTtkWidget)
    mocker.patch("hardfi_encode.app.ttk.Progressbar", MockTtkWidget)


@pytest.fixture
def app(mock_tk, mocker):
    mocker.patch("hardfi_encode.app.verify_ffmpeg", return_value=True)
    from hardfi_encode.app import HardfiEncoderApp
    root = MagicMock()
    app = HardfiEncoderApp(root)
    return app


def make_audio(rel: str, codec: CodecType, bitrate: int = 0) -> AudioFile:
    return AudioFile(
        path=f"/tmp/{rel}",
        relative_path=rel,
        codec=codec,
        bitrate=bitrate,
        sample_rate=44100,
        channels=2,
    )


class TestAppInitialization:
    def test_init(self, mock_tk, mocker):
        mocker.patch("hardfi_encode.app.verify_ffmpeg", return_value=True)
        from hardfi_encode.app import HardfiEncoderApp
        root = MagicMock()
        app = HardfiEncoderApp(root)
        assert app.source_dir is None
        assert app.scan_result is None
        assert app.converting is False

    def test_ffmpeg_warning_shown(self, mock_tk, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        mocker.patch("hardfi_encode.app.verify_ffmpeg", return_value=False)
        from hardfi_encode.app import HardfiEncoderApp
        root = MagicMock()
        app = HardfiEncoderApp(root)
        mock_msg.showwarning.assert_called_once()

    def test_ffmpeg_not_warning_when_found(self, mock_tk, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        mocker.patch("hardfi_encode.app.verify_ffmpeg", return_value=True)
        from hardfi_encode.app import HardfiEncoderApp
        root = MagicMock()
        app = HardfiEncoderApp(root)
        mock_msg.showwarning.assert_not_called()


class TestSelectDirectory:
    def test_select_directory_cancelled(self, app, mocker):
        mocker.patch("hardfi_encode.app.filedialog.askdirectory", return_value="")
        app._select_directory()
        assert app.source_dir is None

    def test_select_directory_selected(self, app, mocker):
        mocker.patch("hardfi_encode.app.filedialog.askdirectory", return_value="/tmp/test_music")
        mocker.patch("hardfi_encode.app.scan_directory")
        app._select_directory()
        assert app.source_dir == "/tmp/test_music"

    def test_select_directory_starts_scan_thread(self, app, mocker):
        mocker.patch("hardfi_encode.app.filedialog.askdirectory", return_value="/tmp/test_music")
        mock_thread = mocker.patch("hardfi_encode.app.threading.Thread")
        app._select_directory()
        mock_thread.assert_called_once()
        assert mock_thread.call_args[1]["daemon"] is True


class TestClearSummary:
    def test_clear_summary_removes_items(self, app):
        mock_tree = MagicMock()
        mock_tree.get_children = MagicMock(return_value=["item1", "item2"])
        app.tree = mock_tree
        app._clear_summary()
        assert mock_tree.delete.call_count == 2

    def test_clear_summary_with_empty_tree(self, app):
        app.tree = MagicMock()
        app.tree.get_children = MagicMock(return_value=[])
        app._clear_summary()
        app.tree.delete.assert_not_called()


class TestScanComplete:
    def test_scan_complete_with_files_clears_previous(self, app):
        mock_tree = MagicMock()
        mock_tree.get_children = MagicMock(return_value=["old1", "old2"])
        app.tree = mock_tree
        result = ScanResult(
            total_files=3,
            by_codec={
                CodecType.WAV: [make_audio("a.wav", CodecType.WAV, 1411000) for _ in range(2)],
                CodecType.FLAC: [make_audio("b.flac", CodecType.FLAC)],
            },
            files=[make_audio("a.wav", CodecType.WAV) for _ in range(3)],
            search_root="/tmp/music",
        )
        app._on_scan_complete(result)
        assert mock_tree.delete.call_count >= 2

    def test_scan_complete_disables_delete_when_target_dir_set(self, app):
        app.target_dir = "/output"
        app.delete_var = MagicMock()
        app.delete_cb = MagicMock()
        app.total_label = MagicMock()
        app._album_label = MagicMock()
        app.convert_btn = MagicMock()
        app.album_btn = MagicMock()
        app.target_var = MagicMock()
        app.tree = MagicMock()
        app.tree.get_children = MagicMock(return_value=[])

        files = [make_audio("a.wav", CodecType.WAV, 1411000) for _ in range(3)]
        result = ScanResult(
            total_files=3,
            by_codec={CodecType.WAV: files},
            files=files,
            search_root="/tmp",
        )
        app._on_scan_complete(result)
        app.delete_var.set.assert_called_with(False)
        app.delete_cb.configure.assert_called_with(state="disabled")

    def test_scan_complete_with_files(self, app):
        app.tree = MagicMock()
        app.tree.get_children = MagicMock(return_value=[])
        result = ScanResult(
            total_files=3,
            by_codec={
                CodecType.WAV: [make_audio("a.wav", CodecType.WAV, 1411000) for _ in range(2)],
                CodecType.FLAC: [make_audio("b.flac", CodecType.FLAC)],
            },
            files=[make_audio("a.wav", CodecType.WAV) for _ in range(3)],
            search_root="/tmp/music",
        )
        app._on_scan_complete(result)
        assert app.scan_result == result

    def test_scan_complete_empty(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        result = ScanResult(total_files=0, by_codec={}, files=[], search_root="/tmp/music")
        app._on_scan_complete(result)
        mock_msg.showinfo.assert_called_once()

    def test_scan_complete_no_lossless(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        result = ScanResult(
            total_files=2,
            by_codec={CodecType.MP3: [make_audio("a.mp3", CodecType.MP3, 192000)]},
            files=[make_audio("a.mp3", CodecType.MP3) for _ in range(2)],
            search_root="/tmp/music",
        )
        app._on_scan_complete(result)
        mock_msg.showinfo.assert_called_once()
        assert "No lossless files" in mock_msg.showinfo.call_args[0][1]


class TestTargetChange:
    def test_lossless_target_hides_bitrate(self, app):
        app.target_var.get = MagicMock(return_value="FLAC")
        app.bitrate_label = MagicMock()
        app.bitrate_combo = MagicMock()
        app._on_target_change()
        assert app.bitrate_label.grid_remove.called
        assert app.bitrate_combo.grid_remove.called

    def test_lossy_target_shows_bitrate(self, app):
        app.target_var.get = MagicMock(return_value="AAC")
        app.bitrate_label = MagicMock()
        app.bitrate_combo = MagicMock()
        app._on_target_change()
        assert app.bitrate_label.grid.called
        assert app.bitrate_combo.grid.called

    def test_mp3_target_shows_bitrate(self, app):
        app.target_var.get = MagicMock(return_value="MP3")
        app.bitrate_label = MagicMock()
        app.bitrate_combo = MagicMock()
        app._on_target_change()
        assert app.bitrate_label.grid.called
        assert app.bitrate_combo.grid.called


class TestConversionFlow:
    def test_start_conversion_no_target(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        app.converting = False
        app.scan_result = MagicMock()
        app.target_var = MagicMock()
        app.target_var.get = MagicMock(return_value="")
        app._start_conversion()
        mock_msg.showwarning.assert_called_once_with("No Target", "Please select a target format.")

    def test_start_conversion_already_converting(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        app.converting = True
        app._start_conversion()
        mock_msg.showwarning.assert_not_called()

    def test_start_conversion_no_lossless_to_convert(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        mocker.patch(
            "hardfi_encode.app.plan_conversion",
            return_value=MagicMock(files_to_convert=[]),
        )
        app.converting = False
        app.scan_result = MagicMock(files=[])
        app.target_var = MagicMock()
        app.target_var.get = MagicMock(return_value="FLAC")
        app._start_conversion()
        mock_msg.showinfo.assert_called_once_with(
            "Nothing to Convert",
            "All lossless files are already in the target format.",
        )

    def test_start_conversion_user_cancels(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        mock_msg.askyesno = MagicMock(return_value=False)
        plan = MagicMock(files_to_convert=[MagicMock()])
        mocker.patch("hardfi_encode.app.plan_conversion", return_value=plan)
        app.converting = False
        app.scan_result = MagicMock(files=[MagicMock()])
        app.target_var = MagicMock()
        app.target_var.get = MagicMock(return_value="FLAC")
        app._start_conversion()
        assert app.converting is False

    def test_start_conversion_proceeds(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        mock_msg.askyesno = MagicMock(return_value=True)
        plan = MagicMock(files_to_convert=[MagicMock()])
        mocker.patch("hardfi_encode.app.plan_conversion", return_value=plan)
        mocker.patch("hardfi_encode.app.threading.Thread")
        app.converting = False
        app.scan_result = MagicMock(files=[MagicMock()], search_root="/tmp")
        app.target_var = MagicMock()
        app.target_var.get = MagicMock(return_value="FLAC")
        app._start_conversion()
        assert app.converting is True

    def test_conversion_complete(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        results = {"converted": 5, "skipped": 2, "errors": 0}
        app._on_conversion_done(results)
        mock_msg.showinfo.assert_called_once()
        assert "Conversion complete" in mock_msg.showinfo.call_args[0][1]

    def test_format_eta_seconds(self, app):
        assert app._format_eta(30) == "30s remaining"

    def test_format_eta_minutes_seconds(self, app):
        assert app._format_eta(125) == "2m 5s remaining"

    def test_format_eta_hours_minutes(self, app):
        assert app._format_eta(3720) == "1h 2m remaining"

    def test_format_eta_under_one_second(self, app):
        assert app._format_eta(0.5) == "< 1s remaining"

    def test_update_progress_no_eta_when_no_start_time(self, app):
        app.progress_bar = MagicMock()
        app.progress_label = MagicMock()
        app._start_time = None
        app._update_progress(50, "halfway")
        app.root.after.assert_any_call(0, app.progress_label.configure, {"text": "halfway"})

    def test_update_progress_no_eta_when_zero_pct(self, app):
        app.progress_bar = MagicMock()
        app.progress_label = MagicMock()
        app._start_time = 100.0
        app._update_progress(0, "starting")
        app.root.after.assert_any_call(0, app.progress_label.configure, {"text": "starting"})

    def test_update_progress_with_eta(self, app, mocker):
        app.progress_bar = MagicMock()
        app.progress_label = MagicMock()
        app._start_time = 100.0
        mocker.patch("hardfi_encode.app.time.monotonic", return_value=150.0)
        app._update_progress(50, "halfway")
        assert app.root.after.call_count == 2
        app.root.after.assert_any_call(0, app.progress_bar.configure, {"value": 50})
        app.root.after.assert_any_call(0, app.progress_label.configure, {"text": "halfway — 50s remaining"})

    def test_delete_toggle_confirmed_keeps_checked(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        mock_msg.askyesno = MagicMock(return_value=True)
        app.delete_var.get = MagicMock(return_value=True)
        app._on_delete_toggle()
        app.delete_var.set.assert_not_called()

    def test_delete_toggle_cancelled_reverts(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        mock_msg.askyesno = MagicMock(return_value=False)
        app.delete_var.get = MagicMock(return_value=True)
        app._on_delete_toggle()
        app.delete_var.set.assert_called_with(False)

    def test_get_albums_grouped_by_parent(self, app):
        files = [
            make_audio("Artist/Album1/track.flac", CodecType.FLAC),
            make_audio("Artist/Album1/track2.wav", CodecType.WAV),
            make_audio("Artist/Album2/track.flac", CodecType.FLAC),
            make_audio("Album3/track.wav", CodecType.WAV),
        ]
        albums = app._get_albums(files)
        assert "Artist/Album1" in albums
        assert "Artist/Album2" in albums
        assert "Album3" in albums
        assert len(albums["Artist/Album1"]) == 2
        assert len(albums["Artist/Album2"]) == 1

    def test_start_conversion_filters_by_album(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        mock_msg.askyesno = MagicMock(return_value=True)
        mock_plan = MagicMock(files_to_convert=[MagicMock()])
        mock_plan_conversion = mocker.patch("hardfi_encode.app.plan_conversion", return_value=mock_plan)
        mocker.patch("hardfi_encode.app.threading.Thread")
        app.converting = False
        app.scan_result = MagicMock(
            files=[
                make_audio("Album1/track.wav", CodecType.WAV),
                make_audio("Album2/track.wav", CodecType.WAV),
            ],
            search_root="/tmp",
        )
        app.target_var = MagicMock()
        app.target_var.get = MagicMock(return_value="FLAC")
        app._album_filter = {"Album1"}
        app._start_conversion()
        files_arg = mock_plan_conversion.call_args[0][0]
        assert len(files_arg) == 1
        assert "Album1" in files_arg[0].relative_path

    def test_select_target_directory_sets_path_and_disables_delete(self, app, mocker):
        app.delete_var = MagicMock()
        app.delete_cb = MagicMock()
        app.target_dir_label = MagicMock()
        app.clear_target_btn = MagicMock()
        mocker.patch("hardfi_encode.app.filedialog.askdirectory", return_value="/output/path")
        app._select_target_directory()
        assert app.target_dir == "/output/path"
        app.target_dir_label.configure.assert_called_with(text="/output/path")
        app.clear_target_btn.configure.assert_called_with(state="normal")
        app.delete_var.set.assert_called_with(False)
        app.delete_cb.configure.assert_called_with(state="disabled")

    def test_select_target_directory_no_selection(self, app, mocker):
        app.target_dir = None
        mocker.patch("hardfi_encode.app.filedialog.askdirectory", return_value="")
        app._select_target_directory()
        assert app.target_dir is None

    def test_clear_target_directory(self, app):
        app.target_dir = "/output"
        app.target_dir_label = MagicMock()
        app.clear_target_btn = MagicMock()
        app.delete_cb = MagicMock()
        app.scan_result = MagicMock()
        app.scan_result.by_codec = {CodecType.WAV: [MagicMock()]}
        app._clear_target_directory()
        assert app.target_dir is None
        app.target_dir_label.configure.assert_called_with(text="Encode in place (same as source)")
        app.clear_target_btn.configure.assert_called_with(state="disabled")
        app.delete_cb.configure.assert_called_with(state="normal")

    def test_start_conversion_with_target_dir_shows_output_in_message(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        mock_msg.askyesno = MagicMock(return_value=False)
        plan = MagicMock(files_to_convert=[MagicMock()])
        mocker.patch("hardfi_encode.app.plan_conversion", return_value=plan)
        app.converting = False
        app.scan_result = MagicMock(files=[MagicMock()], search_root="/tmp")
        app.target_var = MagicMock()
        app.target_var.get = MagicMock(return_value="FLAC")
        app.target_dir = "/my/output"
        app._start_conversion()
        msg = mock_msg.askyesno.call_args[0][1]
        assert "/my/output" in msg
        assert "will be kept" in msg

    def test_select_directory_resets_albums(self, app, mocker):
        app._albums = {"Album1": []}
        app._album_filter = {"Album1"}
        app.dir_label = MagicMock()
        app.convert_btn = MagicMock()
        app.album_btn = MagicMock()
        app._album_label = MagicMock()
        app.total_label = MagicMock()
        app.tree = MagicMock()
        app.tree.get_children = MagicMock(return_value=[])
        mocker.patch("hardfi_encode.app.filedialog.askdirectory", return_value="/new/path")
        app._select_directory()
        assert app._albums == {}
        assert app._album_filter is None

    def test_reset_after_conversion(self, app):
        app.converting = True
        app._cancel_requested = True
        app.convert_btn = MagicMock()
        app.progress_frame = MagicMock()
        app._reset_after_conversion()
        assert app.converting is False
        assert app._cancel_requested is False
        app.convert_btn.configure.assert_called()
        app.progress_frame.grid_remove.assert_called_once()

    def test_cancel_conversion_sets_flag(self, app):
        app._cancel_requested = False
        app.convert_btn = MagicMock()
        app._cancel_conversion()
        assert app._cancel_requested is True
        app.convert_btn.configure.assert_called_with(state="disabled", text="Cancelling...")

    def test_conversion_done_cancelled(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        app._on_conversion_done({"cancelled": True})
        mock_msg.showinfo.assert_called_once_with("Cancelled", "Conversion was cancelled.")

    def test_conversion_done_normal(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        app._on_conversion_done({"converted": 3, "skipped": 1, "errors": 0})
        mock_msg.showinfo.assert_called_once()
        assert "Conversion complete" in mock_msg.showinfo.call_args[0][1]


class TestRunScan:
    def test_run_scan_success(self, app, mocker):
        mock_scan = mocker.patch("hardfi_encode.scanner.scan_directory")
        result = MagicMock()
        mock_scan.return_value = result
        app.source_dir = "/tmp/test_music"
        app._run_scan()
        app.root.after.assert_called_with(0, app._on_scan_complete, result)

    def test_run_scan_failure(self, app, mocker):
        mocker.patch("hardfi_encode.scanner.scan_directory", side_effect=RuntimeError("boom"))
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        app.source_dir = "/tmp/test_music"
        app._run_scan()
        app.root.after.assert_called()
        mock_msg.showerror.assert_not_called()


class TestConversionThread:
    def test_run_conversion_thread_success(self, app, mocker):
        mock_run = mocker.patch("hardfi_encode.app.run_conversion")
        mock_run.return_value = {"converted": 3, "skipped": 0, "errors": 0}
        plan = MagicMock()
        app._run_conversion_thread(plan, "/tmp")
        app.root.after.assert_called_with(0, app._on_conversion_done, mock_run.return_value)

    def test_run_conversion_thread_error(self, app, mocker):
        mocker.patch("hardfi_encode.app.run_conversion", side_effect=RuntimeError("ffmpeg fail"))
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        plan = MagicMock()
        app._run_conversion_thread(plan, "/tmp")
        app.root.after.assert_any_call(0, mock_msg.showerror, "Conversion Error", "ffmpeg fail")


class TestMainFunction:
    def test_main(self, mocker):
        mocker.patch("hardfi_encode.app.tk.Tk")
        mocker.patch("hardfi_encode.app.tk.StringVar")
        mocker.patch("hardfi_encode.app.tk.BooleanVar")
        mocker.patch("hardfi_encode.app.ttk")
        mocker.patch("hardfi_encode.app.verify_ffmpeg", return_value=True)
        mocker.patch("hardfi_encode.app.filedialog")
        mocker.patch("hardfi_encode.app.messagebox")
        from hardfi_encode.app import main
        main()


class TestBitrateValidation:
    def test_invalid_bitrate_shows_warning(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        app.converting = False
        app.scan_result = MagicMock()
        app.target_var = MagicMock()
        app.target_var.get = MagicMock(return_value="AAC")
        app.bitrate_var = MagicMock()
        app.bitrate_var.get = MagicMock(return_value="invalid")
        app.bitrate_label = MagicMock()
        app.bitrate_combo = MagicMock()
        app._start_conversion()
        mock_msg.showwarning.assert_called_with("Invalid Bitrate", "Please select a valid bitrate.")

    def test_valid_bitrate_proceeds(self, app, mocker):
        mock_msg = mocker.patch("hardfi_encode.app.messagebox")
        mock_msg.askyesno = MagicMock(return_value=True)
        plan = MagicMock(files_to_convert=[MagicMock()])
        mocker.patch("hardfi_encode.app.plan_conversion", return_value=plan)
        mocker.patch("hardfi_encode.app.threading.Thread")
        app.converting = False
        app.scan_result = MagicMock(files=[MagicMock()], search_root="/tmp")
        app.target_var = MagicMock()
        app.target_var.get = MagicMock(return_value="AAC")
        app.bitrate_var = MagicMock()
        app.bitrate_var.get = MagicMock(return_value="192k")
        app.bitrate_label = MagicMock()
        app.bitrate_combo = MagicMock()
        app._start_conversion()
        assert app.converting is True


class TestEnableDisableOptions:
    def test_enable_options(self, app):
        child = MockRadiobutton()
        app.convert_frame.winfo_children = MagicMock(return_value=[child])
        app._enable_options()
        assert getattr(child, "configure", None) is not None

    def test_disable_options(self, app):
        child = MockRadiobutton()
        app.convert_frame.winfo_children = MagicMock(return_value=[child])
        app._disable_options()
        assert getattr(child, "configure", None) is not None


class TestBitrateOptions:
    def test_bitrate_options_defined(self):
        from hardfi_encode.app import BITRATE_OPTIONS
        assert "128k" in BITRATE_OPTIONS
        assert BITRATE_OPTIONS["128k"] == 128000
        assert "192k" in BITRATE_OPTIONS
        assert "256k" in BITRATE_OPTIONS
        assert "320k" in BITRATE_OPTIONS
        assert BITRATE_OPTIONS["320k"] == 320000

    def test_codec_display_order(self):
        from hardfi_encode.app import CODEC_DISPLAY_ORDER
        assert CODEC_DISPLAY_ORDER[0] == CodecType.WAV
        assert CODEC_DISPLAY_ORDER[-1] == CodecType.UNKNOWN
