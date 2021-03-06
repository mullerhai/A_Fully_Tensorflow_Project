import tensorflow as tf
from sklearn.metrics import confusion_matrix
import numpy as np

# 打开tensorboard查看讯息
# PS D:\git\tensorflow\code\TensorFlow1\5TensorFlow——CNN\API> tensorboard --logdir ./board

class Network():
    def __init__(self, train_batch_size, test_batch_size, pooling_scale):
        """
        @num_hidden:隐藏层的节点数量
        @batch_size:节省内存，分批处理数据，每一批的数据量
        """

        self.train_batch_size = train_batch_size
        self.test_batch_size = test_batch_size

        # Hyper Parameters
        self.conv_config = []     # list of dict
        self.fc_config = []       # list of dict
        self.conv_weights = []
        self.conv_biases = []
        self.fc_weights = []
        self.fc_biases = []
        self.pooling_scale = pooling_scale
        self.pooling_stride = pooling_scale

        # Graph Related
        self.tf_train_samples = None
        self.tf_train_labels = None
        self.tf_test_samples = None
        self.tf_test_labels = None

        # Statistics
        self.merged =None
        self.train_summaries = []
        self.test_summaries = []

    # 命名关键字参数（参数1，*，参数2，参数3）
    # 如果要限制关键字参数的名字，就可以用命名关键字参数，
    # 例如，只接收patch_size, in_depth, out_depth, activation='relu', pooling=False, name作为关键字参数
    def add_conv(self, *, patch_size, in_depth, out_depth, activation='relu', pooling=False, name):
        """
        @添加存储在self.conv_layer_config中的config
        """
        self.conv_config.append({
            'patch_size':patch_size,
            'in_depth':in_depth,
            'out_depth':out_depth,
            'activation':activation,
            'pooling':pooling,
            'name':name
        })

        with tf.name_scope(name):
            weights = tf.Variable(
                tf.truncated_normal([patch_size, patch_size, in_depth, out_depth], stddev=0.1), name=name + '_weights'
            )
            biases = tf.Variable(tf.constant(0.1, shape=[out_depth]), name=name + '_biases')
            self.conv_weights.append(weights)
            self.conv_biases.append(biases)




    def add_fc(self, *, in_num_nodes, out_num_nodes, activation='relu', name):
        """
        @在self.fc_layer_config中添加fc layer
        """
        self.fc_config.append({
            'in_num_nodes':in_num_nodes,
            'out_num_nodes':out_num_nodes,
            'activation':activation,
            'name':name
        })

        with tf.name_scope(name):
            weights = tf.Variable(
                tf.truncated_normal([in_num_nodes,out_num_nodes], stddev=0.1)
            )
            biases = tf.Variable(tf.constant(0.1, shape=[out_num_nodes]))
            self.fc_weights.append(weights)
            self.fc_biases.append(biases)

            self.train_summaries.append(tf.summary.histogram(str(len(self.fc_weights)) + '_weights', weights))
            self.train_summaries.append(tf.summary.histogram(str(len(self.fc_biases)) + '_biases', biases))


    def define_inputs(self, *, train_samples_shape, train_labels_shape, test_samples_shape):
        # 定义图谱中的各种变量
        with tf.name_scope('inputs'):
            self.tf_train_samples = tf.placeholder(tf.float32, shape=train_samples_shape, name='tf_train_samples')
            self.tf_train_labels = tf.placeholder(tf.float32, shape=train_labels_shape, name='tf_train_labels')
            self.tf_test_samples = tf.placeholder(tf.float32, shape=test_samples_shape, name='tf_test_samples')






    def define_model(self):
        ##### 定义计算图谱
        def model(data_flow, train=True):
            """
            @data:original
            @return:logits
            zip() 函数用于将可迭代的对象作为参数，将对象中对应的元素打包成一个个元组，然后返回由这些元组组成的列表。
            如果各个迭代器的元素个数不一致，则返回列表长度与最短的对象相同，利用 * 号操作符，可以将元组解压为列表。
            >>>a = [1,2,3]
            >>> b = [4,5,6]
            >>> c = [4,5,6,7,8]
            >>> zipped = zip(a,b)     # 打包为元组的列表
            [(1, 4), (2, 5), (3, 6)]
            >>> zip(a,c)              # 元素个数与最短的列表一致
            [(1, 4), (2, 5), (3, 6)]
            >>> zip(*zipped)          # 与 zip 相反，可理解为解压，返回二维矩阵式
            [(1, 2, 3), (4, 5, 6)]
            """
            ##### 定义卷积层
            for i, (weights, biases, config) in enumerate(zip(self.conv_weights, self.conv_biases, self.conv_config)):
                with tf.name_scope(config['name'] + '_model'):
                    with tf.name_scope('convolution'):
                        # 默认 1,1,1,1 stride and SAME padding
                        data_flow = tf.nn.conv2d(data_flow, filter=weights, strides=[1,1,1,1], padding='SAME')
                        data_flow = data_flow + biases

                        if not train:
                            self.visualize_filter_map(data_flow, how_many=config['out_depth'],
                                                      display_size=32 // (i // 2 + 1), name=config['name'] + '_conv')
                    if config['activation'] == 'relu':
                        data_flow = tf.nn.relu(data_flow)
                        if not train:
                            self.visualize_filter_map(data_flow, how_many=config['out_depth'],
                                                      display_size=32 // (i // 2 + 1), name=config['name'] + '_relu')
                    else:
                        raise Exception('Activation Func can only be Relu right now.You passed', config['activation'])

                    if config['pooling']:
                        data_flow = tf.nn.max_pool(
                            data_flow,
                            ksize = [1, self.pooling_scale, self.pooling_scale, 1],
                            strides = [1, self.pooling_stride, self.pooling_stride, 1],
                            padding = 'SAME'
                        )

                        if not train:
                            self.visualize_filter_map(data_flow, how_many=config['out_depth'],
                                                      display_size = 32 // (i // 2 + 1) // 2,
                                                      name = config['name'] + '_pooling')

            ##### 定义全连接层
            for i, (weights ,biases, config) in enumerate(zip(self.fc_weights, self.fc_biases, self.fc_config)):
                if i == 0:
                    shape = data_flow.get_shape().as_list()
                    data_flow = tf.reshape(data_flow, [shape[0], shape[1] * shape[2] * shape[3]])
                with tf.name_scope(config['name'] + 'model'):
                    data_flow = tf.matmul(data_flow, weights) + biases
                    if config['activation'] == 'relu':
                        data_flow = tf.nn.relu(data_flow)
                    elif config['activation'] is None:
                        pass
                    else:
                        raise Exception('Activation Func can only be Relu right now.You passed', config['activation'])
            return data_flow

        ##### 训练计算
        logits = model(self.tf_train_samples)
        with tf.name_scope('loss'):
            self.loss = tf.reduce_mean(
                tf.nn.softmax_cross_entropy_with_logits(logits=logits, labels=self.tf_train_labels)
            )
            self.train_summaries.append(tf.summary.scalar('Loss', self.loss))

        ##### 优化
        with tf.name_scope('optimizer'):
            self.optimizer = tf.train.AdamOptimizer(learning_rate=0.0001).minimize(self.loss)

        ##### 训练预测、验证测试集
        with tf.name_scope('train'):
            self.train_prediction = tf.nn.softmax(logits, name='train_prediction')
        with tf.name_scope('test'):
            self.test_prediction = tf.nn.softmax(model(self.tf_test_samples, train=False), name='test_prediction')

        ##### 注意这里不能随便替换成merge_all
        self.merged_train_summary = tf.summary.merge(self.train_summaries)
        self.merged_test_summary = tf.summary.merge(self.test_summaries)


    def run(self, data_iterator, train_samples, train_labels, test_samples, test_labels):
        """
        用到Session
        """
        # 私有函数
        def print_confusion_matrix(confusionMatrix):
            print('Confusion Matrix')
            for i, line in enumerate(confusionMatrix):
                print(line, line[i] / np.sum(line))
            a = 0
            for i, column in enumerate(np.transpose(confusionMatrix, (1, 0))):
                a += (column[i] / np.sum(column)) * (np.sum(column) / 26000)
                print(column[i] / np.sum(column), )
            print('\n', np.sum(confusionMatrix), a)

        self.writer = tf.summary.FileWriter('./board', tf.get_default_graph())

        with tf.Session(graph=tf.get_default_graph()) as session:
            tf.global_variables_initializer().run()

            # 训练
            print('Start Training')
            # batch 1000
            for i, samples, labels in data_iterator(train_samples, train_labels, self.train_batch_size):
                _, l, predictions, summary = session.run(
                    [self.optimizer, self.loss, self.train_prediction, self.merged_train_summary],
                    feed_dict={self.tf_train_samples: samples, self.tf_train_labels: labels}
                )
                self.writer.add_summary(summary, i)
                # labels is True Labels
                accuracy, _ = self.accuracy(predictions, labels)
                if i % 50 == 0:
                    print('Minibatch loss at step {0}: {1:.4f}'.format(i, l))
                    print('Minibatch accuracy:{0:.4f}'.format(accuracy))

            # 测试
            accuracies = []
            confusionMatrices = []
            for i, samples, labels in data_iterator(test_samples, test_labels, self.test_batch_size):
                print('samples shape', samples.shape)
                result, summary = session.run(
                    [self.test_prediction, self.merged_test_summary],
                    feed_dict={self.tf_test_samples: samples}
                )
                # result = self.test_prediction.eval(feed_dict={self.tf_test_samples: samples})
                self.writer.add_summary(summary, i)
                accuracy, cm = self.accuracy(result, labels, need_confusion_matrix=True)
                accuracies.append(accuracy)
                confusionMatrices.append(cm)
                print('Test Accuracy: {0:.4f}'.format(accuracy))
            print(' Average  Accuracy:', np.average(accuracies))
            print('Standard Deviation:', np.std(accuracies))
            print_confusion_matrix(np.add.reduce(confusionMatrices))


    def accuracy(self, predictions, labels, need_confusion_matrix=False):
        """
        计算预测的正确率与召回率
        @return: accuracy and confusionMatrix as a tuple
        """
        _predictions = np.argmax(predictions, 1)
        _labels = np.argmax(labels, 1)
        cm = confusion_matrix(_labels, _predictions) if need_confusion_matrix else None
        accuracy = (100.0 * np.sum(_predictions == _labels) / predictions.shape[0])
        return accuracy, cm




    def visualize_filter_map(self, tensor, *, how_many, display_size, name):
        print(tensor.get_shape)

        filter_map = tensor[-1]
        print(filter_map.get_shape())

        filter_map = tf.transpose(filter_map, perm=[2, 0, 1])
        print(filter_map.get_shape())

        filter_map = tf.reshape(filter_map, (how_many, display_size, display_size, 1))
        print(how_many)

        self.test_summaries.append(tf.summary.image(name, tensor=filter_map, max_outputs=how_many))
