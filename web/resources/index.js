import 'jquery';
import 'bootstrap';
import Vue from 'vue';

import { BrowserClient } from './browser_client';
import { library } from '@fortawesome/fontawesome-svg-core'
import { faPlay, faFilter } from '@fortawesome/free-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'

library.add(faPlay)
library.add(faFilter)
Vue.component('font-awesome-icon', FontAwesomeIcon)
Vue.config.productionTip = false

const vm = new Vue({
    el: '#main',
    data: {
        client: new BrowserClient('', 8765),
        userId: '',
        playlist: [],
        currentPlaylist: [],
        filterText: '',
        nowPlaying: ''
    },
    methods: {
        onMessage(msg) {
            var obj = JSON.parse(msg);

            if ('err' in obj) {
                console.log(obj);
                return;
            }

            if ('action' in obj && 'msg' in obj) {
                let action = obj['action']
                switch(action) {
                    case 'list':
                        var pl = obj['msg'].sort();
                        this.playlist = pl;
                        this.currentPlaylist = pl;
                        break;
                    case 'playing':
                        this.nowPlaying = obj['msg']
                        break;
                }
            }
        },
        onOpen(data) {
            console.log('Successfully connected!')
            this.getPlaylist();
        },
        playSound(filename) {
            let req = {
                'action': 'play',
                'user_id': this.userId,
                'filename': filename
            };
            this.client.sendMessage(JSON.stringify(req));
        },
        getPlaylist() {
            let req = {
                'action': 'list'
            };
            this.client.sendMessage(JSON.stringify(req));
        },
        filterPlaylist() {
            console.log(this.filterText)
            if (this.filterText && this.playlist) {
                this.currentPlaylist = this.playlist.filter(x => x.includes(this.filterText.replace(' ', '_')));
            } else if (this.playlist) {
                this.currentPlaylist = this.playlist;
            }
        }
    },
    mounted() {
        this.client.connect(this.onMessage, this.onOpen);
    }
});
