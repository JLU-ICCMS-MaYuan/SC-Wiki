if(location.href!=="http://127.0.0.1:5173/account") throw new Error('论文地址已变化');
return {url:location.href,text:document.body.textContent.slice(0,600)};