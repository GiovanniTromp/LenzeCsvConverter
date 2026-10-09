import csv
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lenze_parser import parse_integer
from utils import build_output_file, read_review_csv, edit_parameter_fields


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        settings_patch = patch("gui.default_settings_path", return_value=Path(self.directory.name) / "settings.json")
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        self.path = Path(self.directory.name) / "drive parameters.csv"
        self.valid = ["0xBC44", "004", "0,25", "25", "0x19", "UNSIGNED_16",
                      "Rated power", "kW", "0", "655", "?", "False", "RW",
                      "", "", "P320:004", "1/100"]

    def write_csv(self, rows):
        with self.path.open("w", encoding="utf-8-sig", newline="") as file:
            file.write("Device metadata\n")
            writer = csv.writer(file)
            writer.writerow(["Index", "Subindex"])
            writer.writerows(rows)

    def test_invalid_rows_remain_visible(self):
        rows = [self.valid]
        for column, value in [(0, "wrong"), (1, ""), (3, ""), (3, "text"),
                              (3, "NaN"), (3, "1.2"),
                              (3, str(2**31)), (5, "UNKNOWN")]:
            row = self.valid.copy()
            row[column] = value
            rows.append(row)
        rows.append(["0xBC44", "4"])
        self.write_csv(rows)
        reviewed = read_review_csv(self.path)
        self.assertEqual(len(reviewed), len(rows))
        self.assertEqual(reviewed[0].parameter.raw_value, 25)
        self.assertEqual(reviewed[0].line_number, 3)
        self.assertTrue(all(row.error and row.parameter is None for row in reviewed[1:]))

    def test_display_value_does_not_reject_valid_raw_values(self):
        rows = []
        for display in ("0x00000201", "Enabled", "", "0,25"):
            row = self.valid.copy()
            row[2], row[3], row[5] = display, "513", "BITFIELD_32"
            rows.append(row)
        self.write_csv(rows)
        reviewed = read_review_csv(self.path)
        self.assertTrue(all(not row.error for row in reviewed))
        self.assertTrue(all(row.parameter.raw_value == 513 for row in reviewed))

    def test_strings_and_arrays_are_not_scalar_integers(self):
        rows = []
        for kind, raw in (("VISIBLE_STRING", "MA01"), ("VISIBLE_STRING", "123"),
                          ("Array", "F7B50026"), ("Array", "00000000")):
            row = self.valid.copy()
            row[2], row[3], row[5] = raw, raw, kind
            rows.append(row)
        self.write_csv(rows)
        reviewed = read_review_csv(self.path)
        self.assertTrue(all("not supported" in row.error for row in reviewed))

    def test_unsigned_32_bit_literals_are_preserved(self):
        rows = []
        for kind in ("BITFIELD_32", "UNSIGNED_32"):
            for raw in (2147485249, 2147485121, 3221226369, 4294967295):
                row = self.valid.copy()
                row[2], row[3], row[5] = hex(raw), str(raw), kind
                rows.append(row)
        self.write_csv(rows)
        reviewed = read_review_csv(self.path)
        for row, original in zip(reviewed, rows):
            self.assertFalse(row.error)
            self.assertEqual(row.parameter.raw_value, int(original[3]))
            self.assertIn(original[3] + "$DINT", str(row.parameter))

    def test_unsigned_32_bit_range_is_still_checked(self):
        rows = []
        for kind in ("BITFIELD_32", "UNSIGNED_32"):
            for raw in (-1, 4294967296):
                row = self.valid.copy()
                row[2], row[3], row[5] = str(raw), str(raw), kind
                rows.append(row)
        self.write_csv(rows)
        reviewed = read_review_csv(self.path)
        self.assertTrue(all("supported range" in row.error for row in reviewed))

    def test_export_uses_raw_integer_and_replaces_previous_output(self):
        self.write_csv([self.valid])
        parameter = read_review_csv(self.path)[0].parameter
        output = self.path.with_suffix(".txt")
        output.write_text("old content", encoding="utf-8")
        build_output_file({parameter.group_name: [parameter]}, output)
        text = output.read_text(encoding="utf-8")
        self.assertIn("25$DINT", text)
        self.assertIn("004$USINT", text)
        self.assertIn("Group 3 - Motor control", text)
        self.assertNotIn("old content", text)
        self.assertEqual(list(output.parent.glob("*.tmp")), [])

    def test_leading_zero_decimal_and_hexadecimal(self):
        self.assertEqual(parse_integer("004", "Subindex", 1), 4)
        self.assertEqual(parse_integer("0xBC44", "Index", 1), 48196)

    def test_raw_edits_synchronize_scaled_and_hex_values(self):
        edited = edit_parameter_fields(self.valid, 3, "321", 3)
        self.assertFalse(edited.error)
        self.assertEqual(edited.fields[2:5], ["3,21", "321", "0x0141"])
        self.assertEqual(self.valid[2:5], ["0,25", "25", "0x19"])
        signed = self.valid.copy()
        signed[2], signed[5], signed[16] = "0", "INTEGER_16", ""
        edited = edit_parameter_fields(signed, 3, "-1", 3)
        self.assertFalse(edited.error)
        self.assertEqual(edited.fields[2:5], ["-1", "-1", "0xFFFF"])
        bitfield = signed.copy()
        bitfield[2], bitfield[5] = "0x00000000", "BITFIELD_32"
        edited = edit_parameter_fields(bitfield, 3, "2147485249", 3)
        self.assertFalse(edited.error)
        self.assertEqual(edited.fields[2:5], ["0x80000641", "2147485249", "0x80000641"])

    def test_invalid_raw_edits_do_not_leave_stale_derived_cells(self):
        for value in ("", "wrong", "65536", "-1"):
            edited = edit_parameter_fields(self.valid, 3, value, 3)
            self.assertTrue(edited.error)
            self.assertEqual(edited.fields[2], "")
            self.assertEqual(edited.fields[4], "")
            self.assertIsNone(edited.parameter)
        fields = self.valid.copy()
        fields[16] = "1/0"
        self.assertIn("Display factor", edit_parameter_fields(fields, 3, "10", 3).error)

    def test_value_and_hex_edits_synchronize_all_three_cells(self):
        for column, value in ((2, "3,21"), (2, "3.21"), (4, "0x0141"), (4, "0141h"), (4, "141")):
            edited = edit_parameter_fields(self.valid, column, value, 3)
            self.assertFalse(edited.error)
            self.assertEqual(edited.parameter.raw_value, 321)
            self.assertEqual(edited.fields[4], "0x0141")
            self.assertEqual(Fraction(edited.fields[2].replace(",", ".")), Fraction(321, 100))
        signed = self.valid.copy()
        signed[5], signed[16] = "INTEGER_16", ""
        edited = edit_parameter_fields(signed, 4, "FFFF", 3)
        self.assertFalse(edited.error)
        self.assertEqual(edited.parameter.raw_value, -1)
        self.assertEqual(edited.fields[2:5], ["-1,00", "-1", "0xFFFF"])
        for column, value in ((2, "0.255"), (2, "NaN"), (4, "wrong"), (4, "0x10000")):
            edited = edit_parameter_fields(self.valid, column, value, 3)
            self.assertTrue(edited.error)
            self.assertIsNone(edited.parameter)
            self.assertEqual(edited.fields[3], "")

    def test_missing_header_and_empty_table(self):
        self.path.write_text("not a parameter export", encoding="utf-8")
        with self.assertRaises(ValueError):
            read_review_csv(self.path)
        self.write_csv([])
        with self.assertRaises(ValueError):
            read_review_csv(self.path)

    def test_theme_is_restored_when_reopening(self):
        from gui import ConverterApp
        from app_settings import load_theme
        settings = Path(self.directory.name) / "settings.json"
        for expected, next_theme in (("light", "dark"), ("dark", "light"), ("light", "dark")):
            app = ConverterApp()
            app.withdraw()
            try:
                self.assertEqual(app.theme, expected)
                self.assertEqual(app.theme_button["text"], "Light mode" if expected == "dark" else "Dark mode")
                app.toggle_theme()
                self.assertEqual(load_theme(settings), next_theme)
            finally:
                app.destroy()
        for contents in ("invalid json", '[]', '{"theme":"unknown"}'):
            settings.write_text(contents, encoding="utf-8")
            self.assertEqual(load_theme(settings), "light")

    def test_gui_drop_review_remove_and_export(self):
        from gui import ConverterApp
        from types import SimpleNamespace
        invalid = self.valid.copy()
        invalid[3] = "bad value"
        self.write_csv([self.valid, invalid])
        app = ConverterApp()
        app.withdraw()
        try:
            app.on_drop(SimpleNamespace(data=app.tk.call("list", str(self.path))))
            app.update_idletasks()
            self.assertEqual(len(app.table.get_children()), 1)
            parent = app.table.parent("1")
            self.assertEqual(len(app.table.get_children(parent)), 2)
            self.assertEqual(app.table.item(parent, "text"), "Group 3 - Motor control")
            self.assertIn("invalid", app.table.item(parent, "tags"))
            app.table.item(parent, open=False)
            self.assertFalse(app.table.item(parent, "open"))
            self.assertIn("invalid", app.table.item("1", "tags"))
            self.assertEqual(str(app.export_button["state"]), "disabled")
            app.select_invalid()
            app.remove_selected()
            self.assertNotIn("invalid", app.table.item(parent, "tags"))
            self.assertEqual(str(app.export_button["state"]), "normal")
            output = Path(self.directory.name) / "chosen location.txt"
            app.output_path.set(str(output))
            with patch("gui.messagebox.showinfo") as success:
                app.export()
                success.assert_called_once()
            self.assertIn("25$DINT", output.read_text(encoding="utf-8"))
            self.assertNotIn("bad value", output.read_text(encoding="utf-8"))
            # A new drop replaces the category tree and output destination.
            self.path = self.path.with_name("replacement.csv")
            network = self.valid.copy()
            network[15] = "P522:000"
            self.write_csv([self.valid, network])
            self.assertTrue(app.table.tk.call("bind", app.table._w, "<<Drop>>"))
            app.on_drop(SimpleNamespace(data=app.tk.call("list", str(self.path))))
            self.assertEqual(app.input_path, self.path)
            self.assertEqual(len(app.table.get_children()), 2)
            self.assertEqual(Path(app.output_path.get()).name, "lasal_replacement.txt")
            # Selecting a category and its child removes each row just once.
            category = app.table.parent("1")
            app.table.selection_set([category, "1"])
            app.remove_selected()
            self.assertEqual(len(app.rows), 1)
            self.assertFalse(app.table.exists(category))
        finally:
            app.destroy()

    def test_error_navigation_theme_and_editing(self):
        from gui import ConverterApp
        rows = []
        for index in range(5):
            row = self.valid.copy()
            if index in (1, 3):
                row[3] = "invalid"
            rows.append(row)
        self.write_csv(rows)
        app = ConverterApp()
        try:
            app.load_file(self.path)
            app.update()
            parent = app.table.parent("1")
            app.table.item(parent, open=False)
            app.table.selection_set("0")
            app.table.focus("0")
            app.table.focus_force()
            app.update()
            app.table.event_generate("<F4>")
            app.update()
            self.assertEqual(app.table.selection(), ("1",))
            self.assertTrue(app.table.item(parent, "open"))
            app.table.event_generate("<Shift-F4>")
            app.update()
            self.assertEqual(set(app.table.selection()), {"1", "3"})
            self.assertNotIn("2", app.table.selection())
            app.table.event_generate("<F4>")
            app.update()
            self.assertEqual(app.table.selection(), ("1",))
            app.table.event_generate("<Control-F4>")
            app.update()
            self.assertEqual(set(app.table.selection()), {"1", "3"})
            app.table.selection_set("1")
            # Theme changes preserve table state and custom output paths.
            app.output_path.set(str(self.path.with_name("custom.txt")))
            app.table.item(parent, open=False)
            app.toggle_theme()
            app.update()
            self.assertEqual(app.theme, "dark")
            self.assertEqual(app.table.selection(), ("1",))
            self.assertFalse(app.table.item(parent, "open"))
            self.assertEqual(Path(app.output_path.get()).name, "custom.txt")
            # Fix a raw value through the actual overlay cell editor.
            app.table.item(parent, open=True)
            app.table.see("1")
            app.update()
            app.open_cell_editor("1", "Raw Value")
            self.assertIsNotNone(app.editor)
            editor = app.editor[0]
            editor.delete(0, "end")
            editor.insert(0, "321")
            app.finish_edit()
            self.assertFalse(app.rows["1"].error)
            self.assertEqual(app.rows["1"].parameter.raw_value, 321)
            self.assertEqual(app.rows["1"].fields[2], "3,21")
            self.assertEqual(app.rows["1"].fields[4], "0x0141")
            self.assertEqual(app.table.set("1", "Value"), "3,21")
            self.assertEqual(app.table.set("1", "Raw Hex Value"), "0x0141")
            self.assertEqual(app.error_count.get(), "1")
            self.assertIn("invalid", app.table.item(parent, "tags"))
            # Escape cancels rather than committing an invalid replacement.
            app.update()
            app.open_cell_editor("1", "Raw Value")
            app.editor[0].delete(0, "end")
            app.editor[0].insert(0, "wrong")
            app.cancel_edit()
            self.assertEqual(app.rows["1"].parameter.raw_value, 321)
            app.table.event_generate("<Control-e>")
            app.update()
            self.assertEqual(app.table.selection(), ("3",))
            app.table.event_generate("<Delete>")
            app.update()
            self.assertEqual(app.error_count.get(), "0")
            self.assertEqual(str(app.next_error_button["state"]), "disabled")
            self.assertNotIn("invalid", app.table.item(parent, "tags"))
            # Use the documented keyboard bindings to create the edited TXT.
            app.table.focus_force()
            app.update()
            with patch("gui.messagebox.showinfo"):
                app.event_generate("<Control-s>")
                app.update()
            output = self.path.with_name("custom.txt")
            self.assertIn("321$DINT", output.read_text(encoding="utf-8"))
            self.assertEqual(read_review_csv(self.path)[1].fields[3], "invalid")
            # The export controls fit in the smallest supported window.
            app.geometry("1040x740")
            app.update()
            self.assertGreater(app.export_button.winfo_height(), 0)
            self.assertLessEqual(
                app.export_button.winfo_rooty() + app.export_button.winfo_height(),
                app.winfo_rooty() + app.winfo_height(),
            )
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
