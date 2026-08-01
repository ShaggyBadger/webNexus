window.DMSDashboardSearchMixin = function DMSDashboardSearchMixin() {
  return {
    hubQuery: '',
    requestSeq: 0,
    searchDebounceTimer: null,
    hubResults: null,
    selectedStore: null,
    locationDetail: null,
    loadingSearch: false,
    loadingDetail: false,
    hubError: '',

    onHubInput() {
      if (this.searchDebounceTimer) {
        clearTimeout(this.searchDebounceTimer);
      }
      this.searchDebounceTimer = setTimeout(() => {
        this.runHubSearch();
      }, 300);
    },

    setSearchKeyword(keyword) {
      this.hubQuery = keyword;
      this.runHubSearch();
    },

    runHubSearch() {
      const q = this.hubQuery.trim();
      if (!q || q.length < 2) {
        this.hubResults = null;
        this.hubError = '';
        return;
      }

      this.loadingSearch = true;
      this.hubError = '';
      const seq = ++this.requestSeq;

      fetch(`/dms/api/v1/hub/search/?q=${encodeURIComponent(q)}&limit=20`)
        .then((res) => {
          if (!res.ok) {
            throw new Error(`Server status ${res.status}`);
          }
          return res.json();
        })
        .then((response) => {
          if (seq !== this.requestSeq) return;
          this.loadingSearch = false;
          if (response.status === 'success') {
            this.hubResults = response.data;
          } else {
            this.hubError = response.error?.message || 'Search failed.';
          }
        })
        .catch((err) => {
          if (seq !== this.requestSeq) return;
          this.loadingSearch = false;
          this.hubError = 'Network error executing search.';
        });
    },

    selectLocation(storeNum) {
      this.loadingDetail = true;
      this.selectedStore = storeNum;
      this.locationDetail = null;

      fetch(`/dms/api/v1/hub/location/${storeNum}/summary/`)
        .then((res) => {
          if (!res.ok) {
            throw new Error(`Server status ${res.status}`);
          }
          return res.json();
        })
        .then((response) => {
          this.loadingDetail = false;
          if (response.status === 'success') {
            this.locationDetail = response.data;
          } else {
            this.showAlert(`Failed to load store summary: ${response.error?.message || ''}`, 'error');
          }
        })
        .catch(() => {
          this.loadingDetail = false;
          this.showAlert('Network error fetching store summary.', 'error');
        });
    },

    clearLocationDetail() {
      this.selectedStore = null;
      this.locationDetail = null;
    },
  };
};
