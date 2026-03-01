        #     with open(path, "w", newline="") as f:
        #         writer = csv.writer(f)
        #         writer.writerow(headers)
        #         writer.writerows(self.data_history)
        #     print(f"[INFO] Saved {len(self.data_history)} samples to {path}")
        #     self.log_button.setText("Saved!")
        #     QTimer.singleShot(1000, lambda: self.log_button.setText("Log Data"))
        # except Exception as e:
        #     print(f"[ERROR] Saving CSV: {e}")
