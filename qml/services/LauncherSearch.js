.pragma library
// Rank exact names, prefixes and keywords before subsequences and small typos.
function distance(a, b) {
    if (Math.abs(a.length - b.length) > 2) return 3;
    let previous = [];
    for (let i = 0; i <= b.length; i++) previous.push(i);
    for (let i = 1; i <= a.length; i++) {
        const row = [i];
        for (let j = 1; j <= b.length; j++) row.push(Math.min(row[j - 1] + 1, previous[j] + 1, previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)));
        previous = row;
    }
    return previous[b.length];
}
function score(term, name, other) {
    if (name === term) return 100;
    if (name.startsWith(term)) return 85;
    if (name.includes(term)) return 70;
    if (other.includes(term)) return 55;
    let cursor = 0;
    for (const c of name) if (c === term[cursor]) cursor++;
    if (cursor === term.length) return 40 - Math.min(20, name.length - term.length);
    if (term.length >= 3 && term.length <= 40 && name.split(/\s+/).some(word => distance(term, word) <= Math.min(2, Math.floor(term.length / 3)))) return 20;
    return -1;
}
function apps(query, apps, favorites, onlyFavorites) {
    const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean).slice(0, 8);
    return apps.filter(app => !onlyFavorites || favorites.includes(app.id)).map(app => {
        const scores = terms.map(t => score(t, app.name.toLowerCase(), [app.genericName || "", app.comment || "", ...(app.keywords || [])].join(" ").toLowerCase()));
        return {app: app, score: scores.some(s => s < 0) ? -1 : scores.reduce((a, b) => a + b, 0)};
    }).filter(item => item.score >= 0).sort((a, b) => b.score - a.score || Number(favorites.includes(b.app.id)) - Number(favorites.includes(a.app.id)) || a.app.name.localeCompare(b.app.name)).map(item => item.app);
}
