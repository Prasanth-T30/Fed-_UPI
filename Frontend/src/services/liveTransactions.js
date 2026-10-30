const key = (userId) => `fedupi.live-transactions.${userId}`;

export function saveLiveTransactions(userId, rows) {
  try { localStorage.setItem(key(userId), JSON.stringify(rows)); } catch {}
}

export function getLiveTransactions(userId) {
  try { return JSON.parse(localStorage.getItem(key(userId)) || "[]"); } catch { return []; }
}

export function clearLiveTransactions(userId) {
  try { localStorage.removeItem(key(userId)); } catch {}
}

export function findLiveTransaction(userId, { transactionId, referenceId }) {
  const rows = getLiveTransactions(userId);
  if (transactionId) return rows.find((row) => String(row.transaction_id) === transactionId) || null;
  return rows.find((row) => String(row.txn_ref) === referenceId) || null;
}
