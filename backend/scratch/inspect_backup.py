import os
import pickle

def main():
    backup_file = os.path.join(os.path.dirname(__file__), 'db_backup.pkl')
    if not os.path.exists(backup_file):
        print(f"Backup file not found at {backup_file}")
        return
        
    with open(backup_file, 'rb') as f:
        data = pickle.load(f)
        
    watchlist = data.get('watchlist', [])
    print(f"Found {len(watchlist)} watchlist items in db_backup.pkl:")
    for w in watchlist:
        print(w)

if __name__ == '__main__':
    main()
